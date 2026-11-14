def test_secretary_cannot_use_professional_routes(assert_professional_role_access):
    assert_professional_role_access("secretary", allowed=False)
