class AppointmentAuthorizationPolicy:
    _MANAGERS = frozenset({"manager", "admin"})

    @classmethod
    def can_read_all(cls, actor_type: str | None) -> bool:
        return actor_type in cls._MANAGERS or actor_type == "policy_approver"

    @classmethod
    def can_read_own(cls, actor_type: str | None) -> bool:
        return actor_type == "patient"

    @classmethod
    def can_write(cls, actor_type: str | None) -> bool:
        return actor_type in cls._MANAGERS
