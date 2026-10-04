"""Screen authored text separately from typed dates, hashes and opaque IDs."""
from .pii import scan_text
from .weekly_discovery import canonicalize_url


def require_safe(review):
    texts=[review.get('reason','')]
    texts.extend(v for v in review.get('changes',{}).values() if isinstance(v,str))
    texts.extend(v for k,v in review.get('new_entry',{}).items() if isinstance(v,str))
    for evidence in review.get('evidence',[]):
        texts.append(evidence.get('summary',''))
        url=evidence.get('url','')
        if canonicalize_url(url)!=url:raise ValueError('Unsafe evidence URL')
    if any(not scan_text(text).is_clean for text in texts):raise ValueError('PII findings')

def require_authority(review):
    import json
    import re
    import tomllib
    from pathlib import Path
    from urllib.parse import urlsplit
    root = Path(__file__).resolve().parents[2]
    rows=tomllib.loads((root/'config/sources.toml').read_text())['source']
    # Site evidence has its own explicit allowlist. The protected snapshot
    # registry and its compiled 18 education authorities remain unchanged.
    registry = json.loads((root/'config/site-evidence-publishers.v1.json').read_text())
    if registry.get('schema_version') != 1 or not isinstance(registry.get('publishers'), list):
        raise ValueError('Invalid site evidence publisher registry')
    publishers = {}
    core_ids = {row['publisher_id'] for row in rows}
    for publisher in registry['publishers']:
        identity = publisher.get('id')
        hosts = publisher.get('hosts')
        if (not isinstance(identity, str) or not re.fullmatch(r'[a-z][a-z0-9-]{2,63}', identity)
                or identity in core_ids or identity in publishers
                or type(publisher.get('active')) is not bool
                or not isinstance(hosts, list) or not hosts
                or any(not isinstance(host, str) or not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,}', host) for host in hosts)
                or len(set(hosts)) != len(hosts)):
            raise ValueError('Invalid site evidence publisher authority')
        publishers[identity] = publisher
    for evidence in review.get('evidence',[]):
        url = urlsplit(evidence['url'])
        if url.scheme != 'https' or url.username or url.password or url.port not in (None, 443):
            raise ValueError('Unsafe official evidence URL')
        host=url.hostname or ''
        candidates=[r for r in rows if r.get('publisher_id')==evidence['publisher_id'] and r.get('active') is True]
        allowed=False
        for row in candidates:
            authority=(urlsplit(row['endpoint']).hostname or '').removeprefix('www.')
            if host==authority or host.endswith('.'+authority):allowed=True
        publisher = publishers.get(evidence['publisher_id'])
        if publisher and publisher['active'] and host in publisher['hosts']:
            allowed = True
        if not allowed:raise ValueError('Unregistered official publisher or host')

if __name__=='__main__':
    import json,sys
    try:
        for review in json.load(sys.stdin)['reviews']:
            require_safe(review)
            require_authority(review)
    except (ValueError,KeyError,TypeError):sys.exit(2)
