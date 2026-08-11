from aisearcharab_api.rbac import authorize, permissions_for_role


def test_role_permissions_are_explicit() -> None:
    assert "users:manage" in permissions_for_role("owner")
    assert "users:manage" not in permissions_for_role("admin")
    assert "content:publish" in permissions_for_role("publisher")
    assert "content:write" not in permissions_for_role("publisher")
    assert "content:review" not in permissions_for_role("publisher")
    assert "content:publish" not in permissions_for_role("editor")
    assert "content:read_drafts" in permissions_for_role("reviewer")
    assert "content:read_drafts" not in permissions_for_role("analyst")


def test_authorization_reports_missing_permissions() -> None:
    decision = authorize("editor", ("content:write", "content:publish"))
    assert decision.allowed is False
    assert decision.missing_permissions == ("content:publish",)
