import json
from typing import Any, Dict, List
from pydantic import ValidationError

from .llm import LLMClient
from .schemas import ChatResponse, ConversationState, LoanCreate
from .services import LoanService, ConversationService
from sqlalchemy.ext.asyncio import AsyncSession


SYSTEM_PROMPT = """
You are a loan intake assistant. Your job is to collect the following fields:
- applicant_name (string)
- applicant_email (string email)
- amount (number)
- purpose (string brief purpose)

Rules:
1. Respond ONLY with minified JSON: {"action":"ask|save","question": "...", "missing":[...], "collected": {...}}
2. If any field is missing, set action="ask" and provide a concise follow-up question to get the next missing field.
3. If all fields are present, set action="save" and no question.
4. Keep "missing" ordered by priority: applicant_name, applicant_email, amount, purpose.
5. "collected" must contain every field you already know.
"""


class AgentOrchestrator:
    def __init__(
        self,
        llm: LLMClient,
        loan_service: LoanService,
        conversation_service: ConversationService,
    ):
        self.llm = llm
        self.loan_service = loan_service
        self.conversation_service = conversation_service
        self.required_fields = ["applicant_name", "applicant_email", "amount", "purpose"]

    async def handle_turn(
        self, db: AsyncSession, session_id: str | None, user_reply: str | None
    ) -> ChatResponse:
        state = await self.conversation_service.start_or_load(db, session_id)
        history = [
            msg if isinstance(msg, dict) else msg.model_dump() for msg in state.history
        ]
        if user_reply:
            history.append({"role": "user", "content": user_reply})
            state = await self.conversation_service.update_state(
                db,
                state,
                updates={"collected": {}},
                append_message={"role": "user", "content": user_reply},
            )

        if state.completed and state.loan_id:
            loan = await self.loan_service.get_loan(db, state.loan_id)
            return ChatResponse(
                session_id=state.session_id,
                next_question=None,
                pending_fields=[],
                collected=state.collected,
                completed=True,
                loan=loan,
            )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        llm_answer = await self.llm.chat(messages)
        try:
            parsed = json.loads(llm_answer)
        except json.JSONDecodeError:
            parsed = {"action": "ask", "question": "Can you clarify the last detail?", "missing": self.required_fields, "collected": state.collected}

        collected = state.collected | parsed.get("collected", {})
        missing = [f for f in self.required_fields if f not in collected]

        # If the model didn’t map the last user reply, heuristically assign it to the next missing field
        if user_reply and missing:
            next_field = missing[0]
            if next_field == "amount":
                try:
                    cleaned = user_reply.replace(",", "").replace("$", "").strip()
                    collected[next_field] = float(cleaned)
                except ValueError:
                    pass
            elif next_field == "applicant_email":
                import re

                match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", user_reply)
                collected[next_field] = match.group(0) if match else user_reply
            else:
                collected[next_field] = user_reply
            missing = [f for f in self.required_fields if f not in collected]

        if not missing:
            try:
                loan_payload = LoanCreate(
                    applicant_name=collected["applicant_name"],
                    applicant_email=collected["applicant_email"],
                    amount=float(collected["amount"]),
                    purpose=collected["purpose"],
                    extra={"source": "agent-loop"},
                )
            except (ValidationError, ValueError) as exc:
                invalid_fields = set()
                if isinstance(exc, ValidationError):
                    for err in exc.errors():
                        loc = err.get("loc", [])
                        if loc:
                            field = loc[0]
                            if field in self.required_fields:
                                invalid_fields.add(field)
                else:
                    invalid_fields.add("amount")

                for field in invalid_fields:
                    collected.pop(field, None)
                missing = [f for f in self.required_fields if f not in collected]
            else:
                loan = await self.loan_service.create_loan(db, loan_payload)
                state = await self.conversation_service.attach_loan(
                    db, state, loan.id
                )
                return ChatResponse(
                    session_id=state.session_id,
                    next_question=None,
                    pending_fields=[],
                    collected=state.collected,
                    completed=True,
                    loan=loan,
                )

        # Ask follow-up based on current missing fields (ignore stale LLM question)
        question = self._fallback_question(missing)
        await self.conversation_service.update_state(
            db,
            state,
            updates={"collected": collected},
            append_message={"role": "assistant", "content": question},
        )
        return ChatResponse(
            session_id=state.session_id,
            next_question=question,
            pending_fields=missing,
            collected=collected,
            completed=False,
            loan=None,
        )

    def _fallback_question(self, missing: List[str]) -> str:
        if not missing:
            return "I have all I need. Ready to submit?"
        question_map = {
            "applicant_name": "What is the applicant's full name?",
            "applicant_email": "What's the best email for you?",
            "amount": "How much are you looking to borrow?",
            "purpose": "What will you use the funds for?",
        }
        return question_map.get(missing[0], "Can you share more details?")
