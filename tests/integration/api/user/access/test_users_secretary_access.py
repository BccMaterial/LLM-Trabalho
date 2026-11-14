def test_secretary_user_access_is_limited_to_permitted_self_fields(
    assert_non_admin_user_access,
):
    assert_non_admin_user_access("secretary")
