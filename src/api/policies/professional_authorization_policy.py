class ProfessionalAuthorizationPolicy:
    _MANAGERIAL_USER_TYPES = frozenset({"admin", "manager"})

    @classmethod
    def can_create_professional(cls, actor_type: str | None) -> bool:
        return cls._can_manage(actor_type)

    @classmethod
    def can_list_professionals(cls, actor_type: str | None) -> bool:
        return cls._can_manage(actor_type)

    @classmethod
    def can_read_professional(cls, actor_type: str | None) -> bool:
        return cls._can_manage(actor_type)

    @classmethod
    def can_update_professional(cls, actor_type: str | None) -> bool:
        return cls._can_manage(actor_type)

    @classmethod
    def can_deactivate_professional(cls, actor_type: str | None) -> bool:
        return cls._can_manage(actor_type)

    @classmethod
    def _can_manage(cls, actor_type: str | None) -> bool:
        return actor_type in cls._MANAGERIAL_USER_TYPES
