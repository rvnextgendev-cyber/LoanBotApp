import asyncio
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_session, engine
from .models import Base
from .services import LoanService, ConversationService
from .agent import AgentOrchestrator
from .llm import LLMClient
from .schemas import ChatRequest, ChatResponse, LoanCreate, LoanRead

app = FastAPI(title="LoanBot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm_client = LLMClient()
loan_service = LoanService()
conversation_service = ConversationService()
agent = AgentOrchestrator(llm_client, loan_service, conversation_service)


@app.on_event("startup")
async def startup_event():
    # Simple autoload for tables; swap with Alembic in production.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.post("/loans", response_model=LoanRead)
async def create_loan(payload: LoanCreate, db: AsyncSession = Depends(get_session)):
    loan = await loan_service.create_loan(db, payload)
    return loan


@app.post("/chat/llm-next", response_model=ChatResponse)
async def llm_next(body: ChatRequest, db: AsyncSession = Depends(get_session)):
    return await agent.handle_turn(db, body.session_id, body.user_reply)
