"""Manager-owned transport selection, keyed by service endpoint."""
from urllib.parse import urlsplit, urlunsplit


def endpoint(target):
    url = target if isinstance(target, str) else target['url']
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('A service endpoint must be an absolute HTTP(S) URL')
    port = parts.port
    host = parts.hostname.lower()
    if ':' in host:
        host = '[' + host + ']'
    if port and port != (80 if parts.scheme == 'http' else 443):
        host += ':' + str(port)
    return urlunsplit((parts.scheme, host, parts.path.rstrip('/'), '', ''))


def http_endpoints(config, service):
    return {endpoint(target) for target in getattr(config, service + '_url_list', [])}
