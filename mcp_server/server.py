import os
from mcp.server.fastmcp import FastMCP

from app.llm import LLMClient
from app.services import LoanService, ConversationService
from app.agent import AgentOrchestrator
from app.database import SessionLocal, engine
from app.models import Base

MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "streamable-http")
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8765"))

mcp = FastMCP("loanbot-mcp", host=MCP_HOST, port=MCP_PORT)
llm_client = LLMClient()
loan_service = LoanService()
conversation_service = ConversationService()
agent = AgentOrchestrator(llm_client, loan_service, conversation_service)


async def _session():
    async with SessionLocal() as session:
        yield session


@mcp.tool()
async def list_loans() -> list[dict]:
    """List saved loans."""
    async for db in _session():
        await _ensure_tables()
        result = await db.execute(Base.metadata.tables["loans"].select())
        rows = result.mappings().all()
        return [dict(row) for row in rows]
    return []


@mcp.tool()
async def process_email(email_text: str) -> dict:
    """
    Fully automated run: feed an email text, let the LLaMA agent ask questions if needed,
    and save the loan once all fields are present.
    """
    async for db in _session():
        await _ensure_tables()
        # Seed the conversation with the email text as first user message.
        response = await agent.handle_turn(db, session_id=None, user_reply=email_text)
        # Loop a few times, reusing the email text so heuristic extraction can fill fields.
        for _ in range(6):
            if response.completed or not response.pending_fields:
                break
            response = await agent.handle_turn(
                db, response.session_id, user_reply=email_text
            )
        return {
            "session_id": response.session_id,
            "completed": response.completed,
            "pending": response.pending_fields,
            "collected": response.collected,
            "loan": response.loan.model_dump() if response.loan else None,
        }
    return {}


async def _ensure_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    # Use HTTP transport so the container stays up and is reachable.
    mcp.run(transport=MCP_TRANSPORT)
