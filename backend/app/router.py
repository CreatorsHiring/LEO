import json
from pydantic import ValidationError

from backend.app.config import get_settings
from backend.app.llm.ollama import OllamaClient
from backend.app.models import ChatMessage, Domain, RouteDecision


ROUTER_SYSTEM_PROMPT = """You are only a routing classifier for a local LLM workbench.
You must never answer the user's task.
Return strict JSON with:
{
  "domain": "general" | "code" | "math" | "medical",
  "confidence": number from 0 to 1,
  "rationale": short reason,
  "needs_retrieval": boolean
}

Choose code for programming, debugging, scripts, devops, data pipelines, APIs, and software architecture.
Choose math for calculations, equations, proofs, statistics, optimization, or quantitative reasoning.
Choose medical for healthcare, clinical, drug, diagnosis, symptoms, patient, or biomedical requests.
Choose general for business, document summaries, policy, HR, operations, casual chat, and everything else.
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
        except (json.JSONDecodeError, ValidationError, Exception):
            domain = _heuristic_domain(user_message)
            return RouteDecision(
                domain=domain,
                confidence=0.45,
                rationale="Fallback heuristic used because structured router output was unavailable.",
                needs_retrieval=has_documents and _mentions_documents(user_message),
            )


def _heuristic_domain(text: str) -> Domain:
    lowered = text.lower()
    if any(term in lowered for term in ["python", "javascript", "api", "bug", "code", "script", "sql"]):
        return Domain.code
    if any(term in lowered for term in ["calculate", "equation", "proof", "probability", "integral"]):
        return Domain.math
    if any(term in lowered for term in ["patient", "diagnosis", "medicine", "symptom", "clinical"]):
        return Domain.medical
    return Domain.general


def _mentions_documents(text: str) -> bool:
    lowered = text.lower()
    return any(
        term in lowered
        for term in ["pdf", "doc", "document", "file", "uploaded", "attached", "company", "policy", "manual"]
    )
