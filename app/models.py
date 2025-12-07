from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, DateTime, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    applicant_name: Mapped[str] = mapped_column(String(100))
    applicant_email: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Float)
    purpose: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class LoanSession(Base):
    """
    Conversation session to drive the agent loop for a single loan intake.
    Stores partial answers and conversation history to keep the agent stateful.
    """

    __tablename__ = "loan_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    partial_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    history: Mapped[dict] = mapped_column(JSON, default=dict)  # {"messages":[...]}
    completed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
