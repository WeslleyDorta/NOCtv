"""Bounded, same-origin JSON requests. No credential-bearing redirects."""
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request


class SourceError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class JSONClient:
    def __init__(self, base, headers=None, ca_file=None, allow_http=False):
        self.base = base.rstrip('/') + '/'
        self.origin = urllib.parse.urlsplit(self.base)
        if self.origin.scheme not in (('https', 'http') if allow_http else ('https',)) or not self.origin.hostname or self.origin.username or self.origin.password or self.origin.query or self.origin.fragment:
            raise SourceError('invalid_api_url')
        self.headers = headers or {}
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca_file)))

    def get(self, relative):
        target = urllib.parse.urljoin(self.base, relative)
        parsed = urllib.parse.urlsplit(target)
        if (parsed.scheme, parsed.netloc) != (self.origin.scheme, self.origin.netloc) or parsed.username or parsed.fragment:
            raise SourceError('untrusted_resource')
        req = urllib.request.Request(target, headers={**self.headers, 'Accept': 'application/json'})
        try:
            with self.opener.open(req, timeout=10) as response:
                raw = response.read(8_000_001)
                if len(raw) > 8_000_000:
                    raise SourceError('response_too_large')
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            error.close()
            raise SourceError('http_' + str(error.code)) from None
        except (OSError, ValueError, urllib.error.URLError):
            raise SourceError('connection_or_response_error') from None
