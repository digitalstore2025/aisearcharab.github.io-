import socket

import pytest

from aisearcharab_api.geo.network_security import UnsafeTargetError, resolve_public_target, validate_http_url, validate_redirect


def test_rejects_local_private_metadata_and_cgnat_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(UnsafeTargetError):
        validate_http_url("http://localhost/")
    with pytest.raises(UnsafeTargetError):
        resolve_public_target("http://127.0.0.1/")
    with pytest.raises(UnsafeTargetError):
        resolve_public_target("http://169.254.169.254/latest/meta-data/")
    with pytest.raises(UnsafeTargetError):
        resolve_public_target("http://100.64.0.1/")

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443))],
    )
    with pytest.raises(UnsafeTargetError):
        resolve_public_target("https://internal.example/")


def test_accepts_only_public_dns_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        ],
    )
    target = resolve_public_target("https://example.com/path")
    assert target.host == "example.com"
    assert target.port == 443
    assert target.addresses == ("1.1.1.1", "8.8.8.8")


def test_redirect_is_reresolved_and_private_hop_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_getaddrinfo(host: str, *_args, **_kwargs):
        calls.append(host)
        ip = "1.1.1.1" if host == "safe.example" else "192.168.1.4"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    first = resolve_public_target("https://safe.example/start")
    with pytest.raises(UnsafeTargetError):
        validate_redirect(first, "https://redirected.example/private")
    assert calls == ["safe.example", "redirected.example"]


def test_relative_redirect_is_joined_then_reresolved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 443))],
    )
    first = resolve_public_target("https://safe.example/a/start")
    redirected = validate_redirect(first, "../next")
    assert redirected.url == "https://safe.example/next"
    assert redirected.addresses == ("1.1.1.1",)


def test_rejects_credentials_and_nonstandard_ports() -> None:
    with pytest.raises(UnsafeTargetError):
        validate_http_url("https://user:pass@example.com/")
    with pytest.raises(UnsafeTargetError):
        validate_http_url("https://example.com:8443/")
