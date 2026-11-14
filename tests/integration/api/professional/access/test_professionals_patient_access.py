def test_patient_cannot_use_professional_routes(assert_professional_role_access):
    assert_professional_role_access("patient", allowed=False)
