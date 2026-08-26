from backend.app.models import Domain, ModelConfig


MODEL_REGISTRY: dict[Domain, ModelConfig] = {
    Domain.general: ModelConfig(
        domain=Domain.general,
        model="qwen2.5:3b-instruct",
        temperature=0.3,
        system_prompt=(
            "You are a careful local general-purpose assistant running inside an air-gapped "
            "organization. Answer using only the provided context and user conversation. "
            "When retrieved context is present, cite sources with [filename p.page chunk id]."
        ),
    ),
    Domain.code: ModelConfig(
        domain=Domain.code,
        model="qwen2.5-coder:3b-instruct",
        temperature=0.15,
        system_prompt=(
            "You are a local coding expert. Provide practical, secure code and explain important "
            "tradeoffs. If documents are cited, include source citations."
        ),
    ),
    Domain.math: ModelConfig(
        domain=Domain.math,
        model="qwen2.5-math:1.5b-instruct",
        temperature=0.1,
        system_prompt=(
            "You are a local math expert. Show calculation steps clearly and flag assumptions."
        ),
    ),
    Domain.medical: ModelConfig(
        domain=Domain.medical,
        model="qwen2.5:3b-instruct",
        temperature=0.1,
        system_prompt=(
            "You are a cautious medical information assistant. Provide educational information, "
            "cite local documents when used, and recommend professional clinical judgment for care decisions."
        ),
    ),
}


def get_model_for_domain(domain: Domain) -> ModelConfig:
    return MODEL_REGISTRY.get(domain, MODEL_REGISTRY[Domain.general])
