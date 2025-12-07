from typing import Protocol
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .schemas import LoanCreate


class LoanRepository(Protocol):
    async def create(self, session: AsyncSession, payload: LoanCreate) -> models.Loan:
        ...

    async def get(self, session: AsyncSession, loan_id: int) -> models.Loan | None:
        ...


class SqlAlchemyLoanRepository:
    async def create(self, session: AsyncSession, payload: LoanCreate) -> models.Loan:
        loan = models.Loan(
            applicant_name=payload.applicant_name,
            applicant_email=payload.applicant_email,
            amount=payload.amount,
            purpose=payload.purpose,
            extra=payload.extra or {},
        )
        session.add(loan)
        await session.commit()
        await session.refresh(loan)
        return loan

    async def get(self, session: AsyncSession, loan_id: int) -> models.Loan | None:
        result = await session.execute(
            select(models.Loan).where(models.Loan.id == loan_id)
        )
        return result.scalar_one_or_none()
