from api.services.user_authorization_policy import UserAuthorizationPolicy


def test_only_admin_can_create_list_read_or_deactivate_users():
    assert UserAuthorizationPolicy.can_create_user("admin")
    assert UserAuthorizationPolicy.can_list_users("admin")
    assert UserAuthorizationPolicy.can_read_user("admin")
    assert UserAuthorizationPolicy.can_deactivate_user("admin")
    assert not UserAuthorizationPolicy.can_create_user("patient")
    assert not UserAuthorizationPolicy.can_list_users(None)
    assert not UserAuthorizationPolicy.can_read_user("manager")
    assert not UserAuthorizationPolicy.can_deactivate_user("secretary")
    assert not UserAuthorizationPolicy.can_access_agent("admin")
    assert not UserAuthorizationPolicy.can_access_agent(None)
    assert UserAuthorizationPolicy.can_access_agent("patient")
    assert UserAuthorizationPolicy.can_access_agent("policy_approver")


def test_non_admin_can_only_update_self_without_type_or_status():
    assert UserAuthorizationPolicy.can_update_user(
        "patient",
        is_self=True,
        fields={"nome", "email"},
    )
    assert not UserAuthorizationPolicy.can_update_user(
        "patient",
        is_self=False,
        fields={"nome"},
    )
    assert not UserAuthorizationPolicy.can_update_user(
        "patient",
        is_self=True,
        fields={"type"},
    )
    assert not UserAuthorizationPolicy.can_update_user(
        "patient",
        is_self=True,
        fields={"status"},
    )
    assert UserAuthorizationPolicy.can_update_user(
        "admin",
        is_self=False,
        fields={"type", "status"},
    )
