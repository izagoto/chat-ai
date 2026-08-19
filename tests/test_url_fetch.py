import ipaddress

import pytest

from app.services.url_fetch import UrlFetchError, html_to_text, validate_url


def test_html_to_text_strips_script():
    html = "<html><head><script>alert(1)</script></head><body><h1>Title</h1><p>Hello world</p></body></html>"
    text = html_to_text(html)
    assert "Title" in text
    assert "Hello world" in text
    assert "alert" not in text


def test_validate_url_rejects_non_http():
    with pytest.raises(UrlFetchError):
        validate_url("file:///etc/passwd")
    with pytest.raises(UrlFetchError):
        validate_url("ftp://example.com/file")


def test_validate_url_rejects_credentials():
    with pytest.raises(UrlFetchError):
        validate_url("http://user:pass@example.com/secret")


def test_validate_url_rejects_blocked_hosts():
    with pytest.raises(UrlFetchError):
        validate_url("http://localhost/admin")
    with pytest.raises(UrlFetchError):
        validate_url("http://metadata.google.internal/")


def test_validate_url_rejects_private_ip(monkeypatch):
    monkeypatch.setattr(
        "app.services.url_fetch._resolve_ips",
        lambda host, port: [ipaddress.ip_address("10.0.0.5")],
    )
    with pytest.raises(UrlFetchError, match="not allowed"):
        validate_url("http://intranet.example/docs")


def test_validate_url_rejects_loopback_literal():
    with pytest.raises(UrlFetchError):
        validate_url("http://127.0.0.1/health")
    with pytest.raises(UrlFetchError):
        validate_url("http://[::1]/")


def test_validate_url_rejects_link_local_metadata():
    with pytest.raises(UrlFetchError):
        validate_url("http://169.254.169.254/latest/meta-data")


def test_validate_url_rejects_odd_port():
    with pytest.raises(UrlFetchError):
        validate_url("http://example.com:8080/x")


def test_validate_url_allows_public_ip(monkeypatch):
    monkeypatch.setattr(
        "app.services.url_fetch._resolve_ips",
        lambda host, port: [ipaddress.ip_address("93.184.216.34")],
    )
    assert validate_url("https://example.com/article") == "https://example.com/article"
