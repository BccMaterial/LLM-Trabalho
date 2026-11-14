class MigrationAuthorizationPolicy:
    @staticmethod
    def can_list_migrations(actor_type: str | None) -> bool:
        return actor_type == "admin"

    @staticmethod
    def can_apply_migrations(actor_type: str | None) -> bool:
        return actor_type == "admin"
