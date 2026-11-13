from collections.abc import Collection


class UserAuthorizationPolicy:
    _ADMIN_ONLY_FIELDS = frozenset({"type", "status"})
    _AGENT_USER_TYPES = frozenset(
        {"patient", "manager", "secretary", "policy_approver"}
    )

    @staticmethod
    def can_create_user(actor_type: str | None) -> bool:
        return actor_type == "admin"

    @staticmethod
    def can_list_users(actor_type: str | None) -> bool:
        return actor_type == "admin"

    @staticmethod
    def can_read_user(actor_type: str | None) -> bool:
        return actor_type == "admin"

    @classmethod
    def can_update_user(
        cls,
        actor_type: str | None,
        is_self: bool,
        fields: Collection[str],
    ) -> bool:
        if actor_type == "admin":
            return True
        return is_self and not cls._ADMIN_ONLY_FIELDS.intersection(fields)

    @staticmethod
    def can_deactivate_user(actor_type: str | None) -> bool:
        return actor_type == "admin"

    @classmethod
    def can_access_agent(cls, actor_type: str | None) -> bool:
        return actor_type in cls._AGENT_USER_TYPES
