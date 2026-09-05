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
    import tomllib
    from pathlib import Path
    from urllib.parse import urlsplit
    rows=tomllib.loads((Path(__file__).resolve().parents[2]/'config/sources.toml').read_text())['source']
    for evidence in review.get('evidence',[]):
        host=urlsplit(evidence['url']).hostname or ''
        candidates=[r for r in rows if r.get('publisher_id')==evidence['publisher_id'] and r.get('active') is True]
        allowed=False
        for row in candidates:
            authority=(urlsplit(row['endpoint']).hostname or '').removeprefix('www.')
            if host==authority or host.endswith('.'+authority):allowed=True
        if not allowed:raise ValueError('Unregistered official publisher or host')

if __name__=='__main__':
    import json,sys
    try:
        for review in json.load(sys.stdin)['reviews']:
            require_safe(review)
            require_authority(review)
    except (ValueError,KeyError,TypeError):sys.exit(2)
