import json
import logging

from pydantic import ValidationError

from backend.app.config import get_settings
from backend.app.llm.ollama import OllamaClient
from backend.app.models import ChatMessage, RouteDecision
from backend.app.route_validator import heuristic_fallback_domain

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """You are only a routing classifier for a local LLM workbench.
You must NEVER answer the user's task or provide solutions.
Return strict JSON only, with no extra text:
{
  "domain": "general" | "code" | "math" | "medical",
  "confidence": number from 0 to 1,
  "rationale": "one short sentence",
  "needs_retrieval": boolean
}

Domain definitions:
- code: programming, software development, debugging, scripts, DevOps, APIs, databases, architecture, or any request to write/fix/review code.
- math: calculations, equations, integrals, derivatives, proofs, statistics, probability, optimization, or quantitative reasoning.
- medical: healthcare, clinical care, symptoms, diagnosis, drugs, treatment, patients, or biomedical topics.
- general: business, HR, policy, document summaries, definitions unrelated to the domains above, casual chat, and everything else.

Few-shot routing examples (classify only; never answer):
User: write a java code for hello world
{"domain":"code","confidence":0.95,"rationale":"The user is asking for Java code.","needs_retrieval":false}

User: write a Python function to sort an array
{"domain":"code","confidence":0.95,"rationale":"The user wants a Python programming function.","needs_retrieval":false}

User: debug this Java program
{"domain":"code","confidence":0.93,"rationale":"The user needs help debugging Java code.","needs_retrieval":false}

User: design a REST API
{"domain":"code","confidence":0.90,"rationale":"The user is asking about API software design.","needs_retrieval":false}

User: calculate the probability of two heads
{"domain":"math","confidence":0.92,"rationale":"The user is asking for a probability calculation.","needs_retrieval":false}

User: solve this differential equation
{"domain":"math","confidence":0.93,"rationale":"The user wants help solving a math equation.","needs_retrieval":false}

User: explain what a primary key is
{"domain":"general","confidence":0.88,"rationale":"The user wants a general database concept explained.","needs_retrieval":false}

User: summarize this company policy
{"domain":"general","confidence":0.90,"rationale":"The user wants a business document summarized.","needs_retrieval":true}

Set needs_retrieval true when the user asks about uploaded/company/internal documents, cites files,
asks to summarize attached material, or likely needs private document context."""


class PromptRouter:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = OllamaClient()

    async def route(self, user_message: str, has_documents: bool) -> RouteDecision:
        messages = [
            ChatMessage(role="system", content=ROUTER_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"has_uploaded_documents={has_documents}\n\nUser prompt:\n{user_message}",
            ),
        ]
        try:
            raw = await self.client.chat(
                model=self.settings.router_model,
                messages=messages,
                temperature=0,
                json_mode=True,
            )
            data = json.loads(raw)
            decision = RouteDecision.model_validate(data)
            if has_documents:
                decision.needs_retrieval = decision.needs_retrieval or _mentions_documents(user_message)
            return decision
        except (json.JSONDecodeError, ValidationError, Exception) as exc:
            logger.warning("[ROUTER] structured output unavailable, using heuristic fallback: %s", exc)
            domain = heuristic_fallback_domain(user_message)
            return RouteDecision(
                domain=domain,
                confidence=0.45,
                rationale="Fallback heuristic used because structured router output was unavailable.",
                needs_retrieval=has_documents and _mentions_documents(user_message),
            )


def _mentions_documents(text: str) -> bool:
    lowered = text.lower()
    return any(
        term in lowered
        for term in ["pdf", "doc", "document", "file", "uploaded", "attached", "company", "policy", "manual"]
    )
