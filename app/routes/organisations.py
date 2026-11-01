import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.domain import Role
from app.routes.deps import (
    CanManageMembers,
    CurrentPrincipal,
    get_organisation_repository,
    get_user_repository,
)

router = APIRouter()


class OrganisationResponse(BaseModel):
    id: uuid.UUID
    name: str
    role: Role


class MemberResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: Role


class AddMemberRequest(BaseModel):
    email: EmailStr
    role: Role = Role.MEMBER


@router.get("/organisation")
def current_organisation(principal: CurrentPrincipal) -> OrganisationResponse:
    return OrganisationResponse(
        id=principal.organisation.id,
        name=principal.organisation.name,
        role=principal.role,
    )


@router.get("/organisation/members")
def list_members(principal: CurrentPrincipal) -> list[MemberResponse]:
    """Any member may see who else is in the organisation.

    Reading the roster is not privileged: you already know you have colleagues,
    and hiding it buys nothing while making the product confusing.
    """
    return [
        MemberResponse(id=user.id, email=user.email, role=role)
        for user, role in get_organisation_repository().members(
            principal.organisation.id
        )
    ]


@router.post("/organisation/members", status_code=status.HTTP_201_CREATED)
def add_member(
    request: AddMemberRequest, principal: CanManageMembers
) -> MemberResponse:
    """Add an existing account to this organisation.

    Invitation by email to a non-existent account is a separate feature with
    its own security surface -- a token in an email, an expiry, an acceptance
    flow. This adds someone who has already signed up.
    """
    if request.role is Role.OWNER:
        # Transferring ownership is a different action with different
        # consequences, and deserves its own endpoint rather than hiding
        # inside "add a member".
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Ownership cannot be granted here.",
        )

    user = get_user_repository().get_by_email(request.email.lower())

    if user is None:
        # 404 rather than "no such account": whether an email is registered is
        # not something an arbitrary caller is entitled to learn.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such account.")

    repository = get_organisation_repository()

    existing = repository.membership_for(user.id)

    if existing is not None:
        current, _ = existing

        if current.id == principal.organisation.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Already a member.")

        # Signup gives everyone a personal workspace, so without this every
        # invitation would be refused. Someone who has not used theirs can
        # hand it back; someone who has would lose access to their own data,
        # which is not a trade an invitation should make silently.
        if not repository.is_unused_personal_workspace(current.id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "That account already belongs to an organisation with data in it.",
            )

        repository.remove_member(current.id, user.id)
        repository.discard(current.id)

    repository.add_member(principal.organisation.id, user.id, request.role)
    return MemberResponse(id=user.id, email=user.email, role=request.role)


@router.delete(
    "/organisation/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(user_id: uuid.UUID, principal: CanManageMembers) -> None:
    if user_id == principal.user.id:
        # An organisation with no members is unreachable, and the last owner
        # removing themselves is the usual way to get there by accident.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot remove yourself.")

    removed = get_organisation_repository().remove_member(
        principal.organisation.id, user_id
    )

    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not a member.")
