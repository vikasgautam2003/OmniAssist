import uuid

import pytest

from app.domain import Message, Role, Scope, User
from app.repositories.memory import (
    InMemoryChunkRepository,
    InMemoryConversationRepository,
)
from app.repositories.memory_organisations import InMemoryOrganisationRepository
from tests.fakes import FakeEmbedder


# ---------------------------------------------------------------- roles
def test_only_owners_and_admins_manage_members() -> None:
    assert Role.OWNER.can_manage_members()
    assert Role.ADMIN.can_manage_members()
    assert not Role.MEMBER.can_manage_members()


def test_only_an_owner_deletes_the_organisation() -> None:
    assert Role.OWNER.can_delete_organisation()
    assert not Role.ADMIN.can_delete_organisation()
    assert not Role.MEMBER.can_delete_organisation()


# ---------------------------------------------------------------- membership
def test_a_new_organisation_has_an_owner() -> None:
    repository = InMemoryOrganisationRepository()
    user_id = uuid.uuid4()

    organisation = repository.create_with_owner("Acme", user_id)
    found = repository.membership_for(user_id)

    assert found == (organisation, Role.OWNER)


def test_someone_with_no_membership_resolves_to_nothing() -> None:
    """A user with no organisation must fail, never fall back to a default --
    a shared default tenant is a boundary with a hole in it."""
    assert InMemoryOrganisationRepository().membership_for(uuid.uuid4()) is None


def test_a_member_cannot_be_removed_from_an_organisation_they_are_not_in() -> None:
    repository = InMemoryOrganisationRepository()
    user_id = uuid.uuid4()
    repository.create_with_owner("Acme", user_id)

    assert repository.remove_member(uuid.uuid4(), user_id) is False
    assert repository.membership_for(user_id) is not None


def test_members_lists_only_this_organisation() -> None:
    repository = InMemoryOrganisationRepository()
    a, b = uuid.uuid4(), uuid.uuid4()
    for who in (a, b):
        repository.register_user(User(id=who, email=f"{who}@x", password_hash="x"))

    acme = repository.create_with_owner("Acme", a)
    repository.create_with_owner("Other", b)

    assert [u.id for u, _ in repository.members(acme.id)] == [a]


# ---------------------------------------------------------------- isolation
def test_a_conversation_is_invisible_to_another_organisation(
    scope: Scope, other_scope: Scope
) -> None:
    repository = InMemoryConversationRepository()
    repository.add_message("c1", scope, Message(role="user", content="private"))

    assert repository.get_history("c1", other_scope) == []


def test_a_conversation_is_invisible_to_a_colleague(
    scope: Scope, colleague_scope: Scope
) -> None:
    """Documents are shared across an organisation; chats are not. Sharing a
    tenant must not mean reading each other's conversations."""
    repository = InMemoryConversationRepository()
    repository.add_message("c1", scope, Message(role="user", content="private"))

    assert repository.get_history("c1", colleague_scope) == []


def test_documents_are_shared_with_colleagues(
    scope: Scope, colleague_scope: Scope
) -> None:
    """The one place scope means the organisation rather than the user: a
    shared knowledge base is most of what an organisation is for."""
    chunks = InMemoryChunkRepository()
    embedder = FakeEmbedder()
    texts = ["the refund window is 30 days"]
    chunks.add(
        scope=scope,
        document_name="policy.pdf",
        chunks=texts,
        vectors=embedder.embed_documents(texts),
        model_id=embedder.model_id,
    )

    assert chunks.list_documents(colleague_scope) == ["policy.pdf"]
    found = chunks.search(colleague_scope, embedder.embed_query(texts[0]), limit=5)
    assert found[0].content == texts[0]


def test_documents_are_not_shared_across_organisations(
    scope: Scope, other_scope: Scope
) -> None:
    chunks = InMemoryChunkRepository()
    embedder = FakeEmbedder()
    texts = ["the secret is 42"]
    chunks.add(
        scope=scope,
        document_name="private.pdf",
        chunks=texts,
        vectors=embedder.embed_documents(texts),
        model_id=embedder.model_id,
    )

    assert chunks.list_documents(other_scope) == []
    assert chunks.search(other_scope, embedder.embed_query(texts[0]), limit=5) == []


def test_deleting_a_document_does_not_reach_another_organisation(
    scope: Scope, other_scope: Scope
) -> None:
    chunks = InMemoryChunkRepository()
    embedder = FakeEmbedder()
    for who in (scope, other_scope):
        chunks.add(
            scope=who,
            document_name="shared-name.pdf",
            chunks=["x"],
            vectors=embedder.embed_documents(["x"]),
            model_id=embedder.model_id,
        )

    chunks.delete_document(scope, "shared-name.pdf")

    assert chunks.list_documents(scope) == []
    assert chunks.list_documents(other_scope) == ["shared-name.pdf"]


@pytest.mark.parametrize("field", ["organisation_id", "user_id"])
def test_scope_carries_no_authority(field: str) -> None:
    """Scope answers which rows exist, never what may be done to them --
    authorisation is about the action and belongs in the route."""
    scope = Scope(organisation_id=uuid.uuid4(), user_id=uuid.uuid4())

    assert hasattr(scope, field)
    assert not hasattr(scope, "role")


def test_an_unused_personal_workspace_can_be_handed_back() -> None:
    """Signup gives everyone a workspace, which makes one-org-per-user and
    invitations mutually exclusive unless an unused one can be given up."""
    repository = InMemoryOrganisationRepository()
    joiner = uuid.uuid4()
    personal = repository.create_with_owner("joiner workspace", joiner)

    assert repository.is_unused_personal_workspace(personal.id)


def test_a_workspace_with_other_members_is_not_personal() -> None:
    repository = InMemoryOrganisationRepository()
    owner, colleague = uuid.uuid4(), uuid.uuid4()
    acme = repository.create_with_owner("Acme", owner)
    repository.add_member(acme.id, colleague, Role.MEMBER)

    assert not repository.is_unused_personal_workspace(acme.id)


def test_joining_replaces_the_previous_membership() -> None:
    repository = InMemoryOrganisationRepository()
    owner, joiner = uuid.uuid4(), uuid.uuid4()
    acme = repository.create_with_owner("Acme", owner)
    personal = repository.create_with_owner("joiner workspace", joiner)

    repository.remove_member(personal.id, joiner)
    repository.discard(personal.id)
    repository.add_member(acme.id, joiner, Role.MEMBER)

    found = repository.membership_for(joiner)
    assert found is not None
    assert found[0].id == acme.id
    assert found[1] is Role.MEMBER
