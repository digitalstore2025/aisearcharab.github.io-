from __future__ import annotations

import pytest

from aisearcharab_api.tool_policy import (
    InvalidToolRegistration, MissingToolPermission, ToolApprovalRequired, ToolCapability,
    ToolCapabilityRegistry, ToolIdempotencyKeyRequired, ToolInvocationContext,
    ToolNetworkSourceDenied, UnknownToolError,
)


def test_read_tool_requires_application_permission() -> None:
    registry = ToolCapabilityRegistry([ToolCapability(name="search_repository", required_permissions=frozenset({"content:read"}))])
    with pytest.raises(MissingToolPermission):
        registry.authorize("search_repository", ToolInvocationContext(granted_permissions=frozenset()))
    assert registry.authorize("search_repository", ToolInvocationContext(granted_permissions=frozenset({"content:read"}))).capability.name == "search_repository"


def test_model_cannot_invent_unregistered_tool() -> None:
    with pytest.raises(UnknownToolError):
        ToolCapabilityRegistry([]).authorize("shell_everything", ToolInvocationContext(granted_permissions=frozenset({"*"})))


def test_external_research_tool_requires_explicit_allowlisted_source() -> None:
    registry = ToolCapabilityRegistry([ToolCapability(name="fetch_research_source", required_permissions=frozenset({"research:read"}), replay_class="read_replay_safe", allowed_research_sources=frozenset({"official-docs"}))])
    with pytest.raises(ToolNetworkSourceDenied, match="explicit"):
        registry.authorize("fetch_research_source", ToolInvocationContext(granted_permissions=frozenset({"research:read"})))
    with pytest.raises(ToolNetworkSourceDenied, match="not allowlisted"):
        registry.authorize("fetch_research_source", ToolInvocationContext(granted_permissions=frozenset({"research:read"}), research_source_id="model-invented-source"))
    assert registry.authorize("fetch_research_source", ToolInvocationContext(granted_permissions=frozenset({"research:read"}), research_source_id="official-docs")).research_source_id == "official-docs"


def test_tool_without_network_capability_rejects_source_id() -> None:
    with pytest.raises(ToolNetworkSourceDenied, match="no external research"):
        ToolCapabilityRegistry([ToolCapability(name="local_rank")]).authorize("local_rank", ToolInvocationContext(granted_permissions=frozenset(), research_source_id="official-docs"))


def test_non_idempotent_side_effect_registration_requires_approval_and_permission() -> None:
    with pytest.raises(InvalidToolRegistration, match="must require approval"):
        ToolCapability(name="publish", replay_class="non_idempotent_side_effect", required_permissions=frozenset({"content:publish"}))
    with pytest.raises(InvalidToolRegistration, match="application permission"):
        ToolCapability(name="publish", replay_class="non_idempotent_side_effect", requires_approval=True)
    registry = ToolCapabilityRegistry([ToolCapability(name="publish", replay_class="non_idempotent_side_effect", required_permissions=frozenset({"content:publish"}), requires_approval=True)])
    with pytest.raises(ToolApprovalRequired):
        registry.authorize("publish", ToolInvocationContext(granted_permissions=frozenset({"content:publish"})))


def test_idempotent_side_effect_requires_permission_key_and_invocation_key() -> None:
    with pytest.raises(InvalidToolRegistration, match="idempotency"):
        ToolCapability(name="record_event", replay_class="idempotent_side_effect", required_permissions=frozenset({"events:write"}))
    with pytest.raises(InvalidToolRegistration, match="application permission"):
        ToolCapability(name="record_event", replay_class="idempotent_side_effect", idempotency_key_required=True)
    registry = ToolCapabilityRegistry([ToolCapability(name="record_event", replay_class="idempotent_side_effect", required_permissions=frozenset({"events:write"}), idempotency_key_required=True)])
    with pytest.raises(ToolIdempotencyKeyRequired):
        registry.authorize("record_event", ToolInvocationContext(granted_permissions=frozenset({"events:write"})))
    assert registry.authorize("record_event", ToolInvocationContext(granted_permissions=frozenset({"events:write"}), idempotency_key="request-123")).idempotency_key == "request-123"


def test_network_capable_tool_registration_requires_permission() -> None:
    with pytest.raises(InvalidToolRegistration, match="application permission"):
        ToolCapability(name="fetch_research_source", allowed_research_sources=frozenset({"official-docs"}))


def test_registry_rejects_duplicate_tools() -> None:
    with pytest.raises(InvalidToolRegistration, match="duplicate"):
        ToolCapabilityRegistry([ToolCapability(name="search"), ToolCapability(name="search")])
