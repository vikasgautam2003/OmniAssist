import uuid

from sqlalchemy import delete, func, select

from app.db.models import (
    ArtifactRow,
    Conversation,
    DocumentChunk,
    MembershipRow,
    OrganisationRow,
    UserRow,
)
from app.db.session import get_session_factory
from app.domain import Organisation, Role, User


class PostgresOrganisationRepository:
    def __init__(self) -> None:
        self._session_factory = get_session_factory()

    def create_with_owner(self, name: str, user_id: uuid.UUID) -> Organisation:
        """Create an organisation and make this user its owner.

        One transaction: an organisation with no owner is unreachable, and a
        membership pointing at nothing is worse.
        """
        row = OrganisationRow(name=name)

        with self._session_factory() as session:
            session.add(row)
            session.flush()
            session.add(
                MembershipRow(
                    user_id=user_id,
                    organisation_id=row.id,
                    role=Role.OWNER.value,
                )
            )
            session.commit()
            return Organisation(id=row.id, name=row.name)

    def membership_for(self, user_id: uuid.UUID) -> tuple[Organisation, Role] | None:
        query = (
            select(OrganisationRow, MembershipRow.role)
            .join(MembershipRow, MembershipRow.organisation_id == OrganisationRow.id)
            .where(MembershipRow.user_id == user_id)
        )

        with self._session_factory() as session:
            found = session.execute(query).first()

        if found is None:
            return None

        organisation, role = found
        return (
            Organisation(id=organisation.id, name=organisation.name),
            Role(role),
        )

    def members(self, organisation_id: uuid.UUID) -> list[tuple[User, Role]]:
        query = (
            select(UserRow, MembershipRow.role)
            .join(MembershipRow, MembershipRow.user_id == UserRow.id)
            .where(MembershipRow.organisation_id == organisation_id)
            .order_by(UserRow.email)
        )

        with self._session_factory() as session:
            rows = session.execute(query).all()

        return [
            (
                User(id=u.id, email=u.email, password_hash=u.password_hash),
                Role(role),
            )
            for u, role in rows
        ]

    def add_member(
        self, organisation_id: uuid.UUID, user_id: uuid.UUID, role: Role
    ) -> None:
        with self._session_factory() as session:
            session.add(
                MembershipRow(
                    user_id=user_id,
                    organisation_id=organisation_id,
                    role=role.value,
                )
            )
            session.commit()

    def remove_member(self, organisation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        # organisation_id is in the WHERE clause, as everywhere else: without
        # it an admin of one tenant could remove a member of another.
        where = (
            MembershipRow.organisation_id == organisation_id,
            MembershipRow.user_id == user_id,
        )

        with self._session_factory() as session:
            # Checked before deleting rather than reading rowcount, which
            # SQLAlchemy types as unavailable on a generic Result. Both
            # statements run in one transaction, so nothing can slip between.
            exists = session.scalar(select(MembershipRow.id).where(*where))

            if exists is None:
                return False

            session.execute(delete(MembershipRow).where(*where))
            session.commit()

        return True

    def is_unused_personal_workspace(self, organisation_id: uuid.UUID) -> bool:
        with self._session_factory() as session:
            members = session.scalar(
                select(func.count())
                .select_from(MembershipRow)
                .where(MembershipRow.organisation_id == organisation_id)
            )

            if members != 1:
                return False

            # Any data at all means it has been used, and moving the user
            # would strand it behind a boundary nobody can cross.
            for table in (Conversation, DocumentChunk, ArtifactRow):
                used = session.scalar(
                    select(func.count())
                    .select_from(table)
                    .where(table.organisation_id == organisation_id)
                )
                if used:
                    return False

        return True

    def discard(self, organisation_id: uuid.UUID) -> None:
        with self._session_factory() as session:
            session.execute(
                delete(OrganisationRow).where(OrganisationRow.id == organisation_id)
            )
            session.commit()
