from __future__ import annotations

import socket

import pytest

from aisearcharab_api.research_policy import (
    ResearchPolicyError,
    ResearchSourcePolicy,
    ResearchSourceRegistry,
    ResearchTargetDenied,
    UnknownResearchSource,
    validate_connected_peer,
)


def _source(**overrides: object) -> ResearchSourcePolicy:
    values: dict[str, object] = {
        "source_id": "official-docs",
        "allowed_hosts": frozenset({"docs.example.com"}),
        "allow_subdomains": False,
    }
    values.update(overrides)
    return ResearchSourcePolicy(**values)  # type: ignore[arg-type]


def _public_dns(monkeypatch: pytest.MonkeyPatch, address: str = "1.1.1.1") -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))],
    )


def test_preflight_requires_registered_allowlisted_https_source(monkeypatch: pytest.MonkeyPatch) -> None:
    _public_dns(monkeypatch)
    registry = ResearchSourceRegistry([_source()])
    target = registry.preflight("official-docs", "https://docs.example.com/guide")
    assert target.source_id == "official-docs"
    assert target.resolved.host == "docs.example.com"
    assert target.resolved.addresses == ("1.1.1.1",)
    assert target.max_response_bytes == 2 * 1024 * 1024


def test_unknown_source_fails_before_network_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    def should_not_resolve(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return []
    monkeypatch.setattr(socket, "getaddrinfo", should_not_resolve)
    registry = ResearchSourceRegistry([_source()])
    with pytest.raises(UnknownResearchSource):
        registry.preflight("invented-by-model", "https://docs.example.com/")
    assert calls == 0


def test_unallowlisted_host_fails_before_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    def should_not_resolve(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return []
    monkeypatch.setattr(socket, "getaddrinfo", should_not_resolve)
    registry = ResearchSourceRegistry([_source()])
    with pytest.raises(ResearchTargetDenied, match="not allowlisted"):
        registry.preflight("official-docs", "https://attacker.example/")
    assert calls == 0


def test_subdomain_allowlist_uses_dns_label_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    _public_dns(monkeypatch)
    registry = ResearchSourceRegistry([_source(allowed_hosts=frozenset({"example.com"}), allow_subdomains=True)])
    assert registry.preflight("official-docs", "https://docs.example.com/").resolved.host == "docs.example.com"
    with pytest.raises(ResearchTargetDenied):
        registry.preflight("official-docs", "https://notexample.com/")


def test_private_dns_answer_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _public_dns(monkeypatch, "10.0.0.8")
    registry = ResearchSourceRegistry([_source()])
    with pytest.raises(ResearchTargetDenied, match="non-public"):
        registry.preflight("official-docs", "https://docs.example.com/")


def test_redirect_must_remain_inside_source_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    _public_dns(monkeypatch)
    registry = ResearchSourceRegistry([_source(max_redirects=1)])
    initial = registry.preflight("official-docs", "https://docs.example.com/start")
    redirected = registry.redirect(initial, "/next")
    assert redirected.redirect_count == 1
    with pytest.raises(ResearchTargetDenied, match="redirect limit"):
        registry.redirect(redirected, "/again")
    with pytest.raises(ResearchTargetDenied, match="not allowlisted"):
        registry.redirect(initial, "https://attacker.example/")


def test_connected_peer_must_match_preflight_dns_set(monkeypatch: pytest.MonkeyPatch) -> None:
    _public_dns(monkeypatch, "1.1.1.1")
    registry = ResearchSourceRegistry([_source()])
    target = registry.preflight("official-docs", "https://docs.example.com/")
    assert validate_connected_peer(target, "1.1.1.1") == "1.1.1.1"
    with pytest.raises(ResearchTargetDenied, match="does not match"):
        validate_connected_peer(target, "8.8.8.8")
    with pytest.raises(ResearchTargetDenied, match="not a public"):
        validate_connected_peer(target, "127.0.0.1")


def test_source_policy_rejects_literal_or_local_allowlist_hosts() -> None:
    with pytest.raises(ResearchPolicyError):
        _source(allowed_hosts=frozenset({"127.0.0.1"}))
    with pytest.raises(ResearchPolicyError):
        _source(allowed_hosts=frozenset({"localhost"}))


def test_registry_rejects_duplicate_source_ids() -> None:
    with pytest.raises(ResearchPolicyError, match="duplicate"):
        ResearchSourceRegistry([_source(), _source()])
