import logging
import re

from backend.app.models import Domain, RouteDecision

logger = logging.getLogger(__name__)

HIGH_CONFIDENCE = 0.85
LOW_CONFIDENCE = 0.60

CODE_SIGNALS = [
    "python",
    "java",
    "javascript",
    "typescript",
    "c++",
    "c#",
    "golang",
    "rust",
    "code",
    "coding",
    "program",
    "programming",
    "function",
    "class",
    "method",
    "debug",
    "debugging",
    "compile",
    "api",
    "sql",
    "script",
    "docker",
    "git",
    "react",
    "fastapi",
]

MATH_SIGNALS = [
    "calculate",
    "equation",
    "integral",
    "derivative",
    "probability",
    "statistics",
    "matrix",
    "optimization",
    "proof",
    "theorem",
    "percentage",
]

MEDICAL_SIGNALS = [
    "patient",
    "diagnosis",
    "symptom",
    "symptoms",
    "disease",
    "clinical",
    "medicine",
    "drug",
    "treatment",
    "biomedical",
]

DOMAIN_SIGNALS: dict[Domain, list[str]] = {
    Domain.code: CODE_SIGNALS,
    Domain.math: MATH_SIGNALS,
    Domain.medical: MEDICAL_SIGNALS,
}

RATIONALE_DOMAIN_INDICATORS: dict[Domain, list[str]] = {
    Domain.code: [
        "code",
        "coding",
        "program",
        "programming",
        "debug",
        "api",
        "script",
        "java",
        "python",
        "javascript",
        "software",
        "function",
        "class",
        "rest api",
        "developer",
    ],
    Domain.math: [
        "math",
        "mathematical",
        "calculate",
        "calculation",
        "equation",
        "integral",
        "derivative",
        "probability",
        "statistics",
        "proof",
        "theorem",
        "percentage",
    ],
    Domain.medical: [
        "medical",
        "health",
        "healthcare",
        "patient",
        "symptom",
        "diagnosis",
        "disease",
        "clinical",
        "medicine",
        "drug",
        "treatment",
        "biomedical",
    ],
    Domain.general: [
        "general",
        "business",
        "policy",
        "summary",
        "summarize",
        "explain",
        "casual",
        "conversation",
        "document",
        "company",
    ],
}

DOMAIN_PRIORITY = [Domain.code, Domain.math, Domain.medical, Domain.general]


def _signal_pattern(signal: str) -> re.Pattern[str]:
    if signal in {"c++", "c#"}:
        return re.compile(re.escape(signal), re.IGNORECASE)
    return re.compile(r"\b" + re.escape(signal) + r"\b", re.IGNORECASE)


def count_domain_signals(text: str, domain: Domain) -> int:
    return sum(1 for signal in DOMAIN_SIGNALS[domain] if _signal_pattern(signal).search(text))


def detect_strong_signals(text: str) -> dict[Domain, bool]:
    lowered = text.lower()
    return {
        Domain.code: count_domain_signals(lowered, Domain.code) > 0,
        Domain.math: count_domain_signals(lowered, Domain.math) > 0,
        Domain.medical: count_domain_signals(lowered, Domain.medical) > 0,
    }


def strongest_signal_domain(text: str) -> Domain | None:
    lowered = text.lower()
    scores = {
        domain: count_domain_signals(lowered, domain)
        for domain in (Domain.code, Domain.math, Domain.medical)
    }
    best_score = max(scores.values())
    if best_score == 0:
        return None
    for domain in DOMAIN_PRIORITY:
        if scores[domain] == best_score:
            return domain
    return None


def domain_from_rationale(rationale: str) -> Domain | None:
    lowered = rationale.lower()
    scores = {
        domain: sum(1 for keyword in keywords if keyword in lowered)
        for domain, keywords in RATIONALE_DOMAIN_INDICATORS.items()
    }
    best_score = max(scores.values())
    if best_score == 0:
        return None
    candidates = [domain for domain, score in scores.items() if score == best_score]
    for domain in DOMAIN_PRIORITY:
        if domain in candidates:
            return domain
    return candidates[0]


def rationale_contradicts_domain(domain: Domain, rationale: str) -> bool:
    suggested = domain_from_rationale(rationale)
    return suggested is not None and suggested != domain


def heuristic_fallback_domain(text: str) -> Domain:
    return strongest_signal_domain(text) or Domain.general


class RouteValidator:
    def validate(self, decision: RouteDecision, user_prompt: str) -> RouteDecision:
        logger.info(
            "[ROUTER] domain=%s confidence=%.2f",
            decision.domain.value,
            decision.confidence,
        )
        logger.info('[ROUTER] rationale="%s"', decision.rationale)

        prompt_signals = detect_strong_signals(user_prompt)
        logger.info("[VALIDATOR] strong_code_signals=%s", prompt_signals[Domain.code])
        logger.info("[VALIDATOR] strong_math_signals=%s", prompt_signals[Domain.math])
        logger.info("[VALIDATOR] strong_medical_signals=%s", prompt_signals[Domain.medical])

        signal_domain = strongest_signal_domain(user_prompt)
        rationale_domain = domain_from_rationale(decision.rationale)
        final_domain = decision.domain
        fallback_used = False

        if rationale_contradicts_domain(decision.domain, decision.rationale) and rationale_domain is not None:
            logger.info(
                "[VALIDATOR] contradiction detected: router=%s rationale=%s",
                decision.domain.value,
                rationale_domain.value,
            )
            final_domain = rationale_domain
            fallback_used = True

        if (
            signal_domain is not None
            and signal_domain != final_domain
            and _signals_contradict_router(decision, signal_domain, prompt_signals)
        ):
            logger.info(
                "[VALIDATOR] contradiction detected: router=%s signals=%s",
                final_domain.value,
                signal_domain.value,
            )
            final_domain = signal_domain
            fallback_used = True

        if decision.confidence < LOW_CONFIDENCE and signal_domain is not None and signal_domain != final_domain:
            logger.info(
                "[VALIDATOR] low confidence (%.2f); applying signal fallback=%s",
                decision.confidence,
                signal_domain.value,
            )
            final_domain = signal_domain
            fallback_used = True

        logger.info("[VALIDATOR] final_domain=%s", final_domain.value)
        logger.info("[VALIDATOR] fallback_used=%s", fallback_used)

        if fallback_used:
            return RouteDecision(
                domain=final_domain,
                confidence=decision.confidence,
                rationale=decision.rationale,
                needs_retrieval=decision.needs_retrieval,
            )
        return decision


def _signals_contradict_router(
    decision: RouteDecision,
    signal_domain: Domain,
    prompt_signals: dict[Domain, bool],
) -> bool:
    if not prompt_signals.get(signal_domain, False):
        return False
    return decision.domain != signal_domain
