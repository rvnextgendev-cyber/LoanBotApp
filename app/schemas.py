from pydantic import BaseModel, EmailStr, Field
from typing import Any, Literal


class LoanCreate(BaseModel):
    applicant_name: str = Field(..., examples=["Alex Customer"])
    applicant_email: EmailStr
    amount: float = Field(..., gt=0)
    purpose: str
    extra: dict | None = None


class LoanRead(LoanCreate):
    id: int
    status: str

    class Config:
        from_attributes = True


class ChatTurn(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ConversationState(BaseModel):
    session_id: str
    history: list[ChatTurn]
    collected: dict[str, Any]
    completed: bool = False
    loan_id: int | None = None


class ChatRequest(BaseModel):
    session_id: str
    user_reply: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    next_question: str | None = None
    pending_fields: list[str]
    collected: dict[str, Any]
    completed: bool = False
    loan: LoanRead | None = None
