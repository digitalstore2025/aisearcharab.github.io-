from aisearcharab_api.rbac import authorize, permissions_for_role


def test_role_permissions_are_explicit() -> None:
    assert "users:manage" in permissions_for_role("owner")
    assert "users:manage" not in permissions_for_role("admin")
    assert "content:publish" in permissions_for_role("publisher")
    assert "content:publish" not in permissions_for_role("editor")


def test_authorization_reports_missing_permissions() -> None:
    decision = authorize("editor", ("content:write", "content:publish"))
    assert decision.allowed is False
    assert decision.missing_permissions == ("content:publish",)
