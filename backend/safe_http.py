"""HTTP(S) transport with DNS pinning, verified TLS and redirect revalidation.

No proxy/environment routing; no second hostname resolution at connect time.
The exact fixture origin can only be injected by tests, never through an API/env flag.
"""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit, urljoin


class NetworkPolicyError(ValueError):
    pass


class SafeHTTP:
    def __init__(self, *, test_origin=None, check=lambda: None, timeout=15, deadline=None):
        self.test_origin = test_origin
        self.check = check
        self.timeout = timeout
        self.deadline = deadline or time.monotonic()+120
        self.requests = 0

    def validate(self, url):
        if len(url) > 8192 or any(ord(c) < 33 for c in url) or '\\' in url:
            raise NetworkPolicyError('Liên kết không hợp lệ.')
        try:
            parsed = urlsplit(url)
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError()
            host = parsed.hostname.encode('idna').decode('ascii')
        except (ValueError, UnicodeError):
            raise NetworkPolicyError('Chỉ nhận liên kết HTTP(S), không chứa thông tin đăng nhập.') from None
        fixture = (parsed.scheme, host, port) == self.test_origin
        if not fixture and port not in (80, 443):
            raise NetworkPolicyError('Liên kết chỉ hỗ trợ cổng HTTP(S) tiêu chuẩn.')
        try:
            addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError:
            raise NetworkPolicyError('Không phân giải được tên miền nguồn.') from None
        if not addresses:
            raise NetworkPolicyError('Nguồn không có địa chỉ hợp lệ.')
        for family, _, _, _, endpoint in addresses:
            ip = ipaddress.ip_address(endpoint[0])
            if family not in (socket.AF_INET, socket.AF_INET6) or (not fixture and (not ip.is_global or ip.is_multicast or getattr(ip, 'ipv4_mapped', None))):
                raise NetworkPolicyError('Đã chặn nguồn mạng nội bộ, loopback hoặc địa chỉ dành riêng.')
        return parsed, host, port, addresses

    def open(self, url, *, method='GET', headers=None, data=None):
        for redirect in range(6):
            self.check()
            if time.monotonic() > self.deadline or self.requests >= 80:
                raise NetworkPolicyError('Nguồn vượt giới hạn thời gian hoặc số request.')
            parsed, host, port, addresses = self.validate(url)
            family, _, _, _, endpoint = addresses[0]
            sock = socket.socket(family, socket.SOCK_STREAM)
            sock.settimeout(min(self.timeout, max(1, self.deadline-time.monotonic())))
            self.requests += 1
            connection = http.client.HTTPConnection(host, port, timeout=self.timeout)
            try:
                sock.connect(endpoint)
                if parsed.scheme == 'https':
                    sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
                connection.sock = sock
                path = parsed.path or '/'
                if parsed.query:
                    path += '?' + parsed.query
                outgoing = {'User-Agent': 'Mozilla/5.0 DubiSub/0.1', 'Accept-Encoding': 'identity'}
                forbidden = {'host', 'connection', 'proxy-authorization', 'proxy-connection', 'accept-encoding'}
                outgoing.update({k:v for k,v in (headers or {}).items() if k.lower() not in forbidden})
                connection.request(method, path, body=data, headers=outgoing)
                response = connection.getresponse()
                if response.status in (301,302,303,307,308):
                    location = response.getheader('Location')
                    response.close();connection.close()
                    if not location or redirect == 5:
                        raise NetworkPolicyError('Nguồn chuyển hướng quá nhiều hoặc không hợp lệ.')
                    new = urljoin(url, location)
                    # Do not carry auth/cookies across origins.
                    if urlsplit(new).netloc != parsed.netloc:
                        headers = {k:v for k,v in (headers or {}).items() if k.lower() not in ('authorization','cookie')}
                    if response.status == 303 or (response.status in (301,302) and method == 'POST'):
                        method, data = 'GET', None
                    url = new
                    continue
                return SafeResponse(response, connection, url, self)
            except BaseException:
                sock.close();connection.close()
                raise
        raise NetworkPolicyError('Quá nhiều chuyển hướng.')


class SafeResponse:
    def __init__(self, response, connection, url, client):
        self.raw, self.connection, self.url, self.client = response, connection, url, client
        self.status, self.headers = response.status, response.headers

    def read(self, amount):
        self.client.check()
        if time.monotonic() > self.client.deadline:
            raise NetworkPolicyError('Đã hết thời gian tải nguồn.')
        return self.raw.read(amount)

    def close(self):
        self.raw.close();self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def redact(url):
    try:
        p = urlsplit(url)
        return f'{p.scheme}://{p.hostname}/…'
    except ValueError:
        return '[liên kết đã ẩn]'
