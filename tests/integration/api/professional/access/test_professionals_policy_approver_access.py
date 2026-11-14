def test_policy_approver_cannot_use_professional_routes(
    assert_professional_role_access,
):
    assert_professional_role_access("policy_approver", allowed=False)
