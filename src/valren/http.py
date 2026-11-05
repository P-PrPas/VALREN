"""Small bounded HTTPS transport: pinned public DNS, no redirects/proxies."""
import http.client
import ipaddress
import json
import socket
import signal
import ssl
import threading
import time
from urllib.parse import urlsplit


class RemoteError(RuntimeError):
    def __init__(self, status=0, uncertain=False):
        super().__init__(f"remote request failed ({status})")
        self.status = status
        self.uncertain = uncertain


class FetchDeadline(RuntimeError):
    pass


def public_address(host, port=443):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("remote host resolves to a non-public address")
    return addresses[0][4][0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


class HTTP:
    def __init__(self, allowed_hosts, timeout=20, max_bytes=2_000_000, sleep=time.sleep):
        self.allowed_hosts = set(allowed_hosts)
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.sleep = sleep

    def request(self, method, url, *, payload=None, headers=None, retry_safe=False):
        if threading.current_thread() is not threading.main_thread():
            raise ValueError("HTTP worker must run on the main POSIX thread for deadlines")
        old_handler = signal.getsignal(signal.SIGALRM)
        previous_timer = signal.getitimer(signal.ITIMER_REAL)
        started = time.monotonic()
        def expired(*_):
            raise FetchDeadline()
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, min(previous_timer[0] or 60, 60))
        try:
            return self._request(method, url, payload=payload, headers=headers, retry_safe=retry_safe)
        except FetchDeadline:
            raise RemoteError(uncertain=method != "GET" and not retry_safe) from None
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
            if previous_timer[0]:
                signal.setitimer(signal.ITIMER_REAL, max(.001, previous_timer[0] - (time.monotonic() - started)), previous_timer[1])

    def _request(self, method, url, *, payload=None, headers=None, retry_safe=False):
        parts = urlsplit(url)
        if (parts.scheme != "https" or parts.hostname not in self.allowed_hosts
                or parts.port not in (None, 443) or parts.username or parts.password or parts.fragment):
            raise ValueError("URL outside HTTPS allowlist")
        body = json.dumps(payload).encode() if payload is not None else None
        request_headers = {"User-Agent": "VALREN/0.1 personal-research", "Accept": "application/json",
                           "Accept-Encoding": "identity", **(headers or {})}
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        safe = method == "GET" or retry_safe
        for attempt in range(3 if safe else 1):
            connection = PinnedHTTPS(parts.hostname, public_address(parts.hostname), self.timeout)
            try:
                connection.request(method, parts.path + ("?" + parts.query if parts.query else ""), body, request_headers)
                response = connection.getresponse()
                response_headers = {k.lower(): v for k, v in response.getheaders()}
                data = response.read(self.max_bytes + 1)
                if len(data) > self.max_bytes:
                    raise RemoteError(response.status, uncertain=not safe)
                if 200 <= response.status < 300:
                    return data, response_headers
                if safe and response.status in (429, 500, 502, 503, 504) and attempt < 2:
                    try:
                        delay = float(response_headers.get("retry-after", 2 ** attempt))
                    except ValueError:
                        delay = 60
                    if delay > 30:
                        raise RemoteError(response.status)
                    self.sleep(max(0, delay))
                    continue
                raise RemoteError(response.status, uncertain=not safe and response.status >= 500)
            except (OSError, http.client.HTTPException):
                if safe and attempt < 2:
                    self.sleep(2 ** attempt)
                    continue
                raise RemoteError(uncertain=not safe) from None
            finally:
                connection.close()

    def json(self, method, url, **kwargs):
        data, headers = self.request(method, url, **kwargs)
        try:
            return json.loads(data), headers
        except (ValueError, UnicodeError):
            raise RemoteError(uncertain=method != "GET" and not kwargs.get("retry_safe")) from None
