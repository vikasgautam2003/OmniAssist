import uuid

from app.domain import Organisation, Role, User


class InMemoryOrganisationRepository:
    def __init__(self) -> None:
        self._organisations: dict[uuid.UUID, Organisation] = {}
        self._memberships: dict[uuid.UUID, tuple[uuid.UUID, Role]] = {}
        self._users: dict[uuid.UUID, User] = {}

    def register_user(self, user: User) -> None:
        """Test helper: members() needs a user to return."""
        self._users[user.id] = user

    def create_with_owner(self, name: str, user_id: uuid.UUID) -> Organisation:
        organisation = Organisation(id=uuid.uuid4(), name=name)
        self._organisations[organisation.id] = organisation
        self._memberships[user_id] = (organisation.id, Role.OWNER)
        return organisation

    def membership_for(self, user_id: uuid.UUID) -> tuple[Organisation, Role] | None:
        found = self._memberships.get(user_id)

        if found is None:
            return None

        organisation_id, role = found
        return self._organisations[organisation_id], role

    def members(self, organisation_id: uuid.UUID) -> list[tuple[User, Role]]:
        return [
            (self._users[user_id], role)
            for user_id, (org_id, role) in self._memberships.items()
            if org_id == organisation_id and user_id in self._users
        ]

    def add_member(
        self, organisation_id: uuid.UUID, user_id: uuid.UUID, role: Role
    ) -> None:
        self._memberships[user_id] = (organisation_id, role)

    def remove_member(self, organisation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        found = self._memberships.get(user_id)

        if found is None or found[0] != organisation_id:
            return False

        del self._memberships[user_id]
        return True

    def is_unused_personal_workspace(self, organisation_id: uuid.UUID) -> bool:
        members = [
            user_id
            for user_id, (org_id, _) in self._memberships.items()
            if org_id == organisation_id
        ]
        return len(members) == 1

    def discard(self, organisation_id: uuid.UUID) -> None:
        self._organisations.pop(organisation_id, None)
