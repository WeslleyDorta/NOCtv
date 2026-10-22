"""Small read-only WSGI service. Gunicorn is the deployment HTTP server."""
import base64
import binascii
import hmac
import json
import mimetypes
import os
from pathlib import Path
from .config import load, public
from .collector import Collector
from .brands import catalog
from .diagnostics import Diagnostics

ROOT = Path(__file__).resolve().parent.parent


class Application:
    def __init__(self, config_path=None, start=True):
        self.config = load(config_path or os.environ.get('NOCTV_CONFIG', ROOT / 'config/demo.json'))
        self.user = os.environ.get('NOCTV_USER', '')
        self.password = os.environ.get('NOCTV_PASSWORD', '')
        if self.config['mode'] == 'live' and (not self.user or len(self.password) < 16):
            raise ValueError('Live mode requires NOCTV_USER and NOCTV_PASSWORD (at least 16 characters)')
        self.collector = Collector(self.config)
        self.diagnostics = Diagnostics(self.config)
        if start:
            self.collector.start()

    def authorized(self, env):
        if self.config['mode'] == 'demo':
            return True
        try:
            kind, encoded = env.get('HTTP_AUTHORIZATION', '').split(' ', 1)
            if kind.lower() != 'basic' or len(encoded) > 4096:
                return False
            value = base64.b64decode(encoded, validate=True)
            expected = (self.user + ':' + self.password).encode()
            return hmac.compare_digest(value, expected)
        except (ValueError, binascii.Error):
            return False

    def __call__(self, env, start_response):
        code, mime, body, extra = '200 OK', 'application/json; charset=utf-8', b'', []
        path = env.get('PATH_INFO', '/')
        method = env.get('REQUEST_METHOD', 'GET')
        if path == '/api/v1/diagnostics/run' and method == 'POST':
            if not self.authorized(env):
                code, body = '401 Unauthorized', b'{"error":"authentication_required"}'
                extra.append(('WWW-Authenticate', 'Basic realm="NOCtv", charset="UTF-8"'))
            elif env.get('HTTP_X_NOCTV_REQUEST') != 'diagnostic' or env.get('CONTENT_TYPE', '').split(';')[0] != 'application/json':
                code, body = '403 Forbidden', b'{"error":"Use the NOCtv diagnostic form."}'
            else:
                try:
                    length = int(env.get('CONTENT_LENGTH', '0'))
                    if not 0 < length <= 1024:
                        raise ValueError('invalid length')
                    request = json.loads(env['wsgi.input'].read(length))
                    status, result = self.diagnostics.run(request)
                    labels = {200: 'OK', 400: 'Bad Request', 403: 'Forbidden', 429: 'Too Many Requests', 503: 'Service Unavailable', 504: 'Gateway Timeout'}
                    code, body = f'{status} {labels[status]}', json.dumps(result).encode()
                except (ValueError, UnicodeError):
                    code, body = '400 Bad Request', b'{"error":"Invalid diagnostic request."}'
        elif method not in ('GET', 'HEAD'):
            code, body = '405 Method Not Allowed', b'{"error":"read_only"}'
            extra.append(('Allow', 'GET, HEAD'))
        elif path == '/healthz':
            body = b'{"status":"ok"}'
        elif not self.authorized(env):
            code, body = '401 Unauthorized', b'{"error":"authentication_required"}'
            extra.append(('WWW-Authenticate', 'Basic realm="NOCtv", charset="UTF-8"'))
        elif path == '/api/v1/config':
            body = json.dumps({**public(self.config), 'brands': catalog()}).encode()
        elif path == '/api/v1/snapshot':
            body = json.dumps(self.collector.snapshot(), allow_nan=False).encode()
        elif path == '/api/v1/diagnostics':
            body = json.dumps(self.diagnostics.status()).encode()
        else:
            target = (ROOT / 'web' / ('index.html' if path == '/' else path.lstrip('/'))).resolve()
            if not target.is_relative_to(ROOT / 'web') or not target.is_file() or target.suffix not in ('.html', '.css', '.js', '.svg', '.woff2', '.txt'):
                code, body = '404 Not Found', b'{"error":"not_found"}'
            else:
                mime = mimetypes.guess_type(target)[0] or 'application/octet-stream'
                body = target.read_bytes()
        headers = [('Content-Type', mime), ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'),
            ('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'no-referrer'), ('X-Frame-Options', 'DENY'),
            ('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")]
        start_response(code, headers + extra)
        return [b'' if method == 'HEAD' else body]


def create_app():
    return Application()
