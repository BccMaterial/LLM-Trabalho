from api.policies.professional_authorization_policy import (
    ProfessionalAuthorizationPolicy,
)


def test_agent_can_read_and_manage_professionals():
    assert ProfessionalAuthorizationPolicy.can_list_professionals("agent")
    assert ProfessionalAuthorizationPolicy.can_read_professional("agent")
    assert ProfessionalAuthorizationPolicy.can_create_professional("agent")
    assert ProfessionalAuthorizationPolicy.can_update_professional("agent")
    assert ProfessionalAuthorizationPolicy.can_deactivate_professional("agent")


def test_only_admin_and_manager_keep_existing_professional_permissions():
    policy_checks = (
        ProfessionalAuthorizationPolicy.can_create_professional,
        ProfessionalAuthorizationPolicy.can_list_professionals,
        ProfessionalAuthorizationPolicy.can_read_professional,
        ProfessionalAuthorizationPolicy.can_update_professional,
        ProfessionalAuthorizationPolicy.can_deactivate_professional,
    )

    for can_access in policy_checks:
        assert can_access("admin")
        assert can_access("manager")
        assert not can_access("patient")
        assert not can_access("secretary")
        assert not can_access(None)
