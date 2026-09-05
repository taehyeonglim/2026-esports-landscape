"""Transient article-to-official-link suggestions; no fetched body persistence."""
from urllib.parse import urlsplit
from .weekly_discovery import _fetch_document, parse_homepage, Surface, DiscoveryError
from .recheck import inspect_url


def official_followup(url, allowed_hosts):
    try:
        document=_fetch_document(url)
        links,_=parse_homepage(document,Surface('transient-followup','homepage',url))
        suggested=[]
        for link in links:
            host=urlsplit(link.url).hostname
            if host in allowed_hosts:
                check=inspect_url(link.url)
                suggested.append(check)
                if len(suggested)==5:break
        return {'suggestions':suggested,'status':'suggested' if suggested else 'MANUAL_OFFICIAL_SEARCH_REQUIRED'}
    except (DiscoveryError,OSError):
        return {'suggestions':[],'status':'SOURCE_UNAVAILABLE'}
