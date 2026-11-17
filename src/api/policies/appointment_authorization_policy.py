class AppointmentAuthorizationPolicy:
    _READ_ALL = frozenset({"manager", "admin", "policy_approver", "agent"})
    _WRITERS = frozenset({"manager", "admin", "agent"})

    @classmethod
    def can_read_all(cls, actor_type: str | None) -> bool:
        return actor_type in cls._READ_ALL

    @classmethod
    def can_read_own(cls, actor_type: str | None) -> bool:
        return actor_type == "patient"

    @classmethod
    def can_write(cls, actor_type: str | None) -> bool:
        return actor_type in cls._WRITERS
