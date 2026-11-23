class AppointmentAuthorizationPolicy:
    _READ_ALL = frozenset({"manager", "admin", "policy_approver"})
    _CREATORS = frozenset({"manager", "admin", "patient"})
    _WRITERS = frozenset({"manager", "admin"})
    _AVAILABILITY_READERS = frozenset({"agent"})

    @classmethod
    def can_read_all(cls, actor_type: str | None) -> bool:
        return actor_type in cls._READ_ALL

    @classmethod
    def can_read_own(cls, actor_type: str | None) -> bool:
        return actor_type == "patient"

    @classmethod
    def can_write(cls, actor_type: str | None) -> bool:
        return actor_type in cls._WRITERS

    @classmethod
    def can_create(cls, actor_type: str | None) -> bool:
        return actor_type in cls._CREATORS

    @classmethod
    def can_check_availability(cls, actor_type: str | None) -> bool:
        return actor_type in cls._AVAILABILITY_READERS
