import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AddressType(str, enum.Enum):
    """What a given address is for. A contact may have one of each, or several."""

    HOME = "Home"
    WORK = "Work"
    OTHER = "Other"


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    first_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(40))

    company: Mapped[str | None] = mapped_column(String(200))
    job_title: Mapped[str | None] = mapped_column(String(200))

    # A contact has many addresses, each tagged Home/Work/Other. The rows live in
    # `addresses` and are owned by the contact: deleting one takes its addresses
    # with it, and dropping an address from this list deletes the row.
    addresses: Mapped[list["Address"]] = relationship(
        back_populates="contact",
        cascade="all, delete-orphan",
        order_by="Address.id",
        lazy="selectin",
    )

    notes: Mapped[str | None] = mapped_column(Text)

    # A profile photo stored inline as a base64 data URL (e.g. "data:image/png;base64,...").
    # The in-memory database has no file storage, so the image travels with the row.
    photo: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        nullable=False,
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Contact id={self.id} email={self.email!r}>"


class Address(Base):
    """One postal address belonging to a contact."""

    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    type: Mapped[AddressType] = mapped_column(
        # Stored as the string value ("Home") rather than a native DB enum, so the
        # column reads plainly in SQLite and adding a type later needs no DDL.
        SAEnum(AddressType, native_enum=False, length=10, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=AddressType.HOME,
    )

    street: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(120))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(120))

    contact: Mapped["Contact"] = relationship(back_populates="addresses")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Address id={self.id} contact_id={self.contact_id} type={self.type.value!r}>"
