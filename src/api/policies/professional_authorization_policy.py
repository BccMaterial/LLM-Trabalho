class ProfessionalAuthorizationPolicy:
    _READERS = frozenset({"admin", "manager"})
    _WRITERS = frozenset({"admin", "manager"})

    @classmethod
    def can_create_professional(cls, actor_type: str | None) -> bool:
        return actor_type in cls._WRITERS

    @classmethod
    def can_list_professionals(cls, actor_type: str | None) -> bool:
        return actor_type in cls._READERS

    @staticmethod
    def can_list_active_professionals(actor_type: str | None) -> bool:
        return actor_type in {"admin", "manager", "agent"}

    @classmethod
    def can_read_professional(cls, actor_type: str | None) -> bool:
        return actor_type in cls._READERS

    @classmethod
    def can_update_professional(cls, actor_type: str | None) -> bool:
        return actor_type in cls._WRITERS

    @classmethod
    def can_deactivate_professional(cls, actor_type: str | None) -> bool:
        return actor_type in cls._WRITERS
