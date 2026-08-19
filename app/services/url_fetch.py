from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings

_ALLOWED_SCHEMES = {"http", "https"}
_ALLOWED_PORTS = {80, 443}
_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.internal",
    "kubernetes",
    "kubernetes.default",
    "kubernetes.default.svc",
}
_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home")
_MAX_REDIRECTS = 3


class UrlFetchError(ValueError):
    """Rejected or failed URL fetch (including SSRF blocks)."""


@dataclass
class FetchedUrl:
    final_url: str
    content_type: str
    body: bytes
    artifact_type: str
    segments: list[tuple[str, dict]]


def _normalize_host(host: str) -> str:
    host = host.strip().strip("[]").lower()
    if host.endswith("."):
        host = host[:-1]
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise UrlFetchError("Invalid hostname") from exc
    return host


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.version == 6 and ip.ipv4_mapped is not None:
        return _is_blocked_ip(ip.ipv4_mapped)
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or         ip.is_unspecified
    )


def _host_is_blocked(host: str) -> bool:
    if host in _BLOCKED_HOSTS or host.startswith("localhost"):
        return True
    return any(host.endswith(suffix) for suffix in _BLOCKED_HOST_SUFFIXES)


def _parse_and_check_structure(raw: str) -> tuple[str, str, int]:
    text = (raw or "").strip()
    if not text or len(text) > 2000:
        raise UrlFetchError("URL is empty or too long")
    parsed = urlparse(text)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise UrlFetchError("Only http and https URLs are allowed")
    if parsed.username or parsed.password:
        raise UrlFetchError("URLs with credentials are not allowed")
    if not parsed.hostname:
        raise UrlFetchError("URL is missing a hostname")
    host = _normalize_host(parsed.hostname)
    if _host_is_blocked(host):
        raise UrlFetchError("That hostname is not allowed")
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    if port not in _ALLOWED_PORTS:
        raise UrlFetchError("Only ports 80 and 443 are allowed")
    return text, host, port


def _resolve_ips(host: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        as_ip = ipaddress.ip_address(host)
        return [as_ip]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UrlFetchError("Could not resolve hostname") from exc
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        addr = info[4][0]
        try:
            ips.append(ipaddress.ip_address(addr))
        except ValueError:
            continue
    if not ips:
        raise UrlFetchError("Could not resolve hostname")
    return ips


def validate_url(raw: str) -> str:
    """Raise UrlFetchError if the URL must not be fetched. Returns the original URL."""
    text, host, port = _parse_and_check_structure(raw)
    for ip in _resolve_ips(host, port):
        if _is_blocked_ip(ip):
            raise UrlFetchError("That address is not allowed")
    return text


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip += 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text)


def html_to_text(html: str) -> str:
    parser = _HTMLText()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\n{3,}", "\n\n", " ".join(parser.parts)).strip()


def _segments_from_text(text: str, url: str) -> list[tuple[str, dict]]:
    cleaned = text.strip()
    if not cleaned:
        return [("(empty page)", {"type": "url", "url": url})]
    blocks = [b.strip() for b in re.split(r"\n{2,}", cleaned) if b.strip()]
    if not blocks:
        blocks = [cleaned]
    return [(block, {"type": "url", "url": url}) for block in blocks[:80]]


def filename_for_url(url: str) -> str:
    host = urlparse(url).hostname or "page"
    host = _normalize_host(host)
    safe = re.sub(r"[^a-z0-9.-]", "-", host)[:80] or "page"
    return f"{safe}.url.html"


async def fetch_url(raw: str) -> FetchedUrl:
    current = validate_url(raw)
    timeout = httpx.Timeout(settings.url_fetch_timeout_seconds)
    max_bytes = settings.url_max_bytes
    headers = {
        "User-Agent": "Alder-Ingest/0.2",
        "Accept": "text/html,application/xhtml+xml,text/plain,application/json;q=0.9,*/*;q=0.1",
    }

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        for _ in range(_MAX_REDIRECTS + 1):
            validate_url(current)
            try:
                async with client.stream("GET", current, headers=headers) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise UrlFetchError("Redirect is missing a Location header")
                        current = validate_url(urljoin(current, location))
                        continue
                    if response.status_code != 200:
                        raise UrlFetchError(f"URL returned HTTP {response.status_code}")
                    chunks: list[bytes] = []
                    total = 0
                    async for part in response.aiter_bytes():
                        total += len(part)
                        if total > max_bytes:
                            raise UrlFetchError("Response is too large")
                        chunks.append(part)
                    body = b"".join(chunks)
                    content_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
                    final_url = str(response.url) if response.url else current
            except UrlFetchError:
                raise
            except httpx.HTTPError as exc:
                raise UrlFetchError("Failed to fetch URL") from exc

            artifact, segments = _body_to_segments(final_url, content_type, body)
            return FetchedUrl(
                final_url=final_url,
                content_type=content_type,
                body=body,
                artifact_type=artifact,
                segments=segments,
            )

    raise UrlFetchError("Too many redirects")


def _body_to_segments(url: str, content_type: str, body: bytes) -> tuple[str, list[tuple[str, dict]]]:
    if content_type in {"text/html", "application/xhtml+xml"} or (not content_type and body.lstrip()[:1] == b"<"):
        text = html_to_text(body.decode("utf-8", errors="ignore"))
        return "url", _segments_from_text(text, url)
    if content_type.startswith("text/"):
        return "url", _segments_from_text(body.decode("utf-8", errors="ignore"), url)
    if content_type in {"application/json", "text/json"}:
        return "url", _segments_from_text(body.decode("utf-8", errors="ignore"), url)
    raise UrlFetchError(f"Unsupported content type: {content_type or 'unknown'}")
