"""
Role hierarchy
--------------
Creator (4) > Admin (3) > Analyst (2) > User (1)

can_manage() encodes the permission rules:
  - Higher level can act on strictly lower levels.
  - Nobody can ever manage a Creator account, regardless of level.
"""


class RoleType:
    USER = "user"
    ANALYST = "analyst"
    ADMIN = "admin"
    CREATOR = "creator"

    PRESET_ASSIGNABLE = [USER, ANALYST, ADMIN]
    ALL = [USER, ANALYST, ADMIN, CREATOR]

    LEVELS = {USER: 1, ANALYST: 2, ADMIN: 3, CREATOR: 4}
    LABELS = {USER: "User", ANALYST: "Analyst", ADMIN: "Admin", CREATOR: "Creator"}


class Role:
    def __init__(self, name: str):
        if name not in RoleType.ALL:
            raise ValueError(f"Invalid role: {name}")
        self.name = name
        self.level = RoleType.LEVELS[name]

    def can_manage(self, target: "Role") -> bool:
        if target.name == RoleType.CREATOR:
            return False
        return self.level > target.level

    def can_assign(self, target_role_name: str) -> bool:
        if target_role_name == RoleType.CREATOR:
            return False
        return self.can_manage(Role(target_role_name))

    def label(self) -> str:
        return RoleType.LABELS[self.name]

    def __eq__(self, other):
        return isinstance(other, Role) and self.name == other.name

    def __repr__(self):
        return f"Role({self.name})"
