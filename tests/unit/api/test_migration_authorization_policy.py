from api.policies.migration_authorization_policy import MigrationAuthorizationPolicy


def test_only_admin_can_manage_migrations():
    assert MigrationAuthorizationPolicy.can_list_migrations("admin")
    assert MigrationAuthorizationPolicy.can_apply_migrations("admin")
    assert not MigrationAuthorizationPolicy.can_list_migrations("manager")
    assert not MigrationAuthorizationPolicy.can_apply_migrations("patient")
    assert not MigrationAuthorizationPolicy.can_apply_migrations(None)
