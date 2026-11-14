def test_patient_cannot_access_migrations(assert_non_admin_migration_access):
    assert_non_admin_migration_access("patient")
