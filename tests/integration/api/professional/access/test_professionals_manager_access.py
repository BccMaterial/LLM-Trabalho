def test_manager_can_use_professional_routes(assert_professional_role_access):
    assert_professional_role_access("manager", allowed=True)
