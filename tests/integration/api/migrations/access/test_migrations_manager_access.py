def test_manager_cannot_access_migrations(assert_non_admin_migration_access):
    assert_non_admin_migration_access("manager")
