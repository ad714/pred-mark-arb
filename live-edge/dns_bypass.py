import socket
import time

import requests

DOH_ENDPOINTS = [
    "https://cloudflare-dns.com/dns-query",
    "https://dns.google/resolve",
]
PATCHED_SUFFIXES = ("polymarket.com",)

_cache = {}
_original_getaddrinfo = socket.getaddrinfo


class ResolutionFailed(RuntimeError):
    pass


def resolve_via_doh(hostname):
    cached = _cache.get(hostname)
    if cached and cached[1] > time.time():
        return cached[0]

    errors = []
    for endpoint in DOH_ENDPOINTS:
        try:
            response = requests.get(
                endpoint,
                params={"name": hostname, "type": "A"},
                headers={"accept": "application/dns-json"},
                timeout=10,
            )
            response.raise_for_status()
            answers = response.json().get("Answer") or []
            addresses = [a["data"] for a in answers if a.get("type") == 1]
            if addresses:
                ttl = min((a.get("TTL", 60) for a in answers), default=60)
                _cache[hostname] = (addresses, time.time() + max(ttl, 30))
                return addresses
            errors.append(f"{endpoint}: no A records")
        except (requests.RequestException, ValueError, KeyError) as exc:
            errors.append(f"{endpoint}: {type(exc).__name__}")

    raise ResolutionFailed(f"could not resolve {hostname} via DoH ({'; '.join(errors)})")


def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if isinstance(host, str) and host.endswith(PATCHED_SUFFIXES):
        try:
            return _original_getaddrinfo(host, port, family, type, proto, flags)
        except socket.gaierror:
            results = []
            for address in resolve_via_doh(host):
                results.append(
                    (socket.AF_INET, type or socket.SOCK_STREAM, proto, "", (address, port))
                )
            if results:
                return results
    return _original_getaddrinfo(host, port, family, type, proto, flags)


def install():
    if socket.getaddrinfo is not _patched_getaddrinfo:
        socket.getaddrinfo = _patched_getaddrinfo


def selftest():
    install()
    for host in ("gamma-api.polymarket.com", "clob.polymarket.com", "data-api.polymarket.com"):
        try:
            addresses = resolve_via_doh(host)
            print(f"  {host:<32} -> {', '.join(addresses[:2])}")
        except ResolutionFailed as exc:
            print(f"  {host:<32} -> FAILED: {exc}")


if __name__ == "__main__":
    print("DoH resolution:")
    selftest()
    install()
    print("\nlive fetch through patched resolver:")
    for url in (
        "https://gamma-api.polymarket.com/markets?limit=1&closed=false",
        "https://data-api.polymarket.com/trades?limit=1",
    ):
        try:
            r = requests.get(url, timeout=15)
            print(f"  HTTP {r.status_code}  {len(r.content):>7} bytes  {url}")
        except requests.RequestException as exc:
            print(f"  FAILED {type(exc).__name__}  {url}")
