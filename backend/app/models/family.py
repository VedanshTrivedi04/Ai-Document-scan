"""
`families` and `family_members`: a household whose documents one person, the
head, submits and manages.

The head is a user of the company; the other members are not users and have
no sign-in. Each identity case can belong to one member
(`cases.family_member_id`), so a family is a set of people each with their
own document bundle. The head is also a member, with relation `self`.
"""
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.company import TenantScopedMixin

RELATION_SELF = "self"
RELATIONS = (RELATION_SELF, "spouse", "son", "daughter", "father", "mother", "other")
CHILD_RELATIONS = ("son", "daughter")
PARENT_RELATIONS = ("father", "mother")


class Family(TenantScopedMixin, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "families"
    # A user heads at most one family.
    __table_args__ = (UniqueConstraint("head_user_id", name="uq_families_head_user_id"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    head_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    members = relationship(
        "FamilyMember", back_populates="family", order_by="FamilyMember.created_at", cascade="all, delete-orphan"
    )


class FamilyMember(TenantScopedMixin, UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "family_members"

    family_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("families.id"), nullable=False, index=True
    )
    # As the head entered them; the documents are checked against these.
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relation: Mapped[str] = mapped_column(String(16), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    family = relationship("Family", back_populates="members")
    cases = relationship("Case", back_populates="family_member", order_by="Case.created_at")
