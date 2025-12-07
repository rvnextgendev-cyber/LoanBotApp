import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .repository import LoanRepository, SqlAlchemyLoanRepository
from .schemas import LoanCreate, ConversationState


class LoanService:
    def __init__(self, repository: LoanRepository | None = None):
        self.repository = repository or SqlAlchemyLoanRepository()

    async def create_loan(self, session: AsyncSession, payload: LoanCreate) -> models.Loan:
        return await self.repository.create(session, payload)

    async def get_loan(self, session: AsyncSession, loan_id: int) -> models.Loan | None:
        return await self.repository.get(session, loan_id)


class ConversationService:
    def __init__(self):
        pass

    async def start_or_load(
        self, session: AsyncSession, session_id: str | None
    ) -> ConversationState:
        conversation_id = session_id or uuid.uuid4().hex
        record = await self._get_record(session, conversation_id)
        if not record:
            record = models.LoanSession(
                conversation_id=conversation_id,
                partial_fields={},
                history={"messages": []},
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)

        history_messages = record.history.get("messages", [])
        return ConversationState(
            session_id=conversation_id,
            history=history_messages,
            collected=record.partial_fields,
            completed=record.completed,
            loan_id=record.partial_fields.get("loan_id"),
        )

    async def update_state(
        self,
        session: AsyncSession,
        state: ConversationState,
        updates: dict[str, Any],
        append_message: dict[str, Any] | None = None,
    ) -> ConversationState:
        record = await self._get_record(session, state.session_id)
        if not record:
            raise ValueError(f"Conversation {state.session_id} not found")

        if append_message:
            history = list(record.history.get("messages", []))
            history.append(append_message)
            record.history = {"messages": history}

        new_fields = dict(record.partial_fields or {})
        new_fields.update(updates.get("collected", {}))
        record.partial_fields = new_fields
        record.completed = updates.get("completed", record.completed)
        await session.commit()
        await session.refresh(record)
        return ConversationState(
            session_id=state.session_id,
            history=record.history["messages"],
            collected=record.partial_fields,
            completed=record.completed,
            loan_id=record.partial_fields.get("loan_id"),
        )

    async def attach_loan(
        self, session: AsyncSession, state: ConversationState, loan_id: int
    ) -> ConversationState:
        record = await self._get_record(session, state.session_id)
        if not record:
            raise ValueError(f"Conversation {state.session_id} not found")
        new_fields = dict(record.partial_fields or {})
        new_fields["loan_id"] = loan_id
        record.partial_fields = new_fields
        record.completed = True
        await session.commit()
        await session.refresh(record)
        return ConversationState(
            session_id=state.session_id,
            history=record.history["messages"],
            collected=record.partial_fields,
            completed=True,
            loan_id=loan_id,
        )

    async def _get_record(
        self, session: AsyncSession, conversation_id: str
    ) -> models.LoanSession | None:
        result = await session.execute(
            select(models.LoanSession).where(
                models.LoanSession.conversation_id == conversation_id
            )
        )
        return result.scalar_one_or_none()
