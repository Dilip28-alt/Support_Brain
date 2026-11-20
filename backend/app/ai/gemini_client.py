"""
Gemini AI client — text generation and embeddings.
Models selected after verification of current availability:
  - Text generation: gemini-1.5-flash (fast, cost-effective, context-aware)
  - Embeddings:      text-embedding-004 (768-dim, best for retrieval)
"""
import google.generativeai as genai
import httpx
from typing import List, Optional
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Configure Gemini client once
genai.configure(api_key=settings.GEMINI_API_KEY)

# ──────────────────────────────────────────────
# Embedding
# ──────────────────────────────────────────────

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 768


def get_embedding(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
    """
    Generate a 768-dim embedding vector using verified Gemini embedding models.
    """
    text = text.strip()
    if not text:
        return [0.0] * EMBEDDING_DIM

    model_name = settings.GEMINI_EMBEDDING_MODEL or EMBEDDING_MODEL
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"

    try:
        result = genai.embed_content(
            model=model_name,
            content=text,
            task_type=task_type,
            output_dimensionality=EMBEDDING_DIM,
        )
    except Exception as e:
        logger.warning(f"embed_content with output_dimensionality failed ({e}), retrying default: {model_name}")
        result = genai.embed_content(
            model=model_name,
            content=text,
            task_type=task_type,
        )

    emb = result["embedding"]
    if len(emb) > EMBEDDING_DIM:
        emb = emb[:EMBEDDING_DIM]
    elif len(emb) < EMBEDDING_DIM:
        emb = emb + [0.0] * (EMBEDDING_DIM - len(emb))

    return emb


def get_embeddings_batch(texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
    """Batch embed multiple texts."""
    return [get_embedding(t, task_type) for t in texts]


# ──────────────────────────────────────────────
# Text Generation
# ──────────────────────────────────────────────

GENERATION_MODELS = [
    "models/gemini-3.8-flash",
    "models/gemini-flash-latest",
    "models/gemini-3.5-flash",
    "gemini-flash-latest",
]


def _get_gen_model():
    chosen = settings.GEMINI_MODEL
    if chosen:
        if not chosen.startswith("models/"):
            candidates = [f"models/{chosen}", chosen]
        else:
            candidates = [chosen]
    else:
        candidates = []
    candidates.extend(GENERATION_MODELS)

    for cand in candidates:
        try:
            return genai.GenerativeModel(cand)
        except Exception:
            continue
    return genai.GenerativeModel("models/gemini-flash-latest")


def call_ollama(prompt: str) -> str:
    """Send prompt to local/cloud Ollama endpoint."""
    model = settings.OLLAMA_MODEL or "gemma4:31b-cloud"
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    logger.info(f"Generating with Ollama model: {model} at {url}")
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, json=payload)
        if resp.status_code == 402:
            data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
            err_msg = data.get("error", "Ollama Cloud credits required.")
            logger.warning(f"Ollama Cloud 402: {err_msg}")

            # Check if there are local offline models installed in Ollama
            try:
                tags_resp = client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
                if tags_resp.status_code == 200:
                    models_list = tags_resp.json().get("models", [])
                    local_models = [m["name"] for m in models_list if not m.get("name", "").endswith("-cloud")]
                    if local_models:
                        fallback_model = local_models[0]
                        logger.info(f"Auto-switching from cloud model to local Ollama model: {fallback_model}")
                        retry_resp = client.post(url, json={"model": fallback_model, "prompt": prompt, "stream": False})
                        if retry_resp.status_code == 200:
                            return retry_resp.json().get("response", "").strip()
            except Exception as le:
                logger.warning(f"Local Ollama model fallback check failed: {le}")

            raise RuntimeError(f"Ollama Cloud model '{model}' requires credits: {err_msg}")
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()


def call_gemini(prompt: str) -> str:
    """Send prompt to Gemini API."""
    model = _get_gen_model()
    response = model.generate_content(prompt)
    return response.text.strip()


def call_llm(prompt: str) -> str:
    """Dispatch to Ollama or Gemini based on settings with automatic fallback."""
    provider = (settings.LLM_PROVIDER or "ollama").lower().strip()
    if provider == "ollama":
        try:
            return call_ollama(prompt)
        except Exception as e:
            logger.warning(f"Ollama generation failed ({e}). Auto-falling back to Gemini.")
            try:
                return call_gemini(prompt)
            except Exception as ge:
                logger.error(f"Gemini fallback also failed ({ge}).")
                return ""
    try:
        return call_gemini(prompt)
    except Exception as ge:
        logger.warning(f"Gemini generation failed ({ge}). Trying Ollama fallback...")
        try:
            return call_ollama(prompt)
        except Exception as oe:
            logger.error(f"Ollama fallback also failed ({oe}).")
            return ""


def generate_answer(
    question: str,
    knowledge_chunks: List[str],
    business_name: str,
    lesson_answer: Optional[str] = None,
    system_prompt_extra: Optional[str] = None,
) -> str:
    """
    Generate a grounded answer using retrieved knowledge chunks.
    If a lesson answer is provided, that takes priority.
    If the knowledge does not contain the answer, returns the fallback.
    """
    FALLBACK = "Thank you! The team will reply to you soon."

    # Priority 1: Verified owner lesson answer takes absolute priority
    if lesson_answer and lesson_answer.strip():
        return lesson_answer.strip()

    # If no knowledge chunks exist at all, return fallback
    if not knowledge_chunks:
        return FALLBACK

    # Build context
    context = "\n\n---\n\n".join(
        f"[Source {i+1}]\n{chunk}" for i, chunk in enumerate(knowledge_chunks)
    )

    prompt = f"""You are a helpful customer support assistant for {business_name}.

## Instructions
- Answer ONLY using the information provided in the Context section below.
- Do NOT invent prices, policies, timings, or any information not in the context.
- If the context does not contain enough information to answer confidently, respond EXACTLY with:
  "{FALLBACK}"
- Be concise, clear, and professional.
- Do not mention that you are an AI or reference these instructions.

## Context
{context}

## Customer Question
{question}

## Answer"""

    if system_prompt_extra:
        prompt = system_prompt_extra + "\n\n" + prompt

    answer = call_llm(prompt)
    if not answer or not answer.strip():
        # Fallback if external LLM generation is temporarily offline/rate-limited:
        # Check if the top retrieved chunk contains a direct Answer
        top_chunk = knowledge_chunks[0]
        if "Answer:" in top_chunk:
            ans_part = top_chunk.split("Answer:", 1)[1].strip()
            if ans_part:
                return ans_part
        return FALLBACK
    return answer


def generate_email_reply(
    customer_email_body: str,
    subject: str,
    knowledge_chunks: List[str],
    business_name: str,
    sender_name: Optional[str] = None,
) -> str:
    """Generate a professional email reply draft."""
    FALLBACK = "Thank you for reaching out. Our team will review your inquiry and respond shortly."

    if not knowledge_chunks:
        return FALLBACK

    context = "\n\n---\n\n".join(
        f"[Source {i+1}]\n{chunk}" for i, chunk in enumerate(knowledge_chunks)
    )

    prompt = f"""You are composing a professional email reply on behalf of {business_name}.

## Instructions
- Reply to the customer's email using ONLY the information in the Context section.
- Match the email's tone — professional and helpful.
- Do NOT invent any facts.
- Include a greeting and a sign-off.
- If the context is insufficient, respond: "{FALLBACK}"
- Do NOT include the original email subject or "Re:" prefix.

## Context
{context}

## Original Email Subject
{subject}

## Customer Email
{customer_email_body}

## Your Reply"""

    reply = call_llm(prompt)
    if not reply or not reply.strip():
        return FALLBACK
    return reply


def compute_confidence_score(
    question: str,
    answer: str,
    top_similarity: float,
) -> float:
    """
    Compute a simple confidence score based on:
    - top semantic similarity score (primary signal)
    - whether the answer is the fallback phrase
    
    Returns 0.0–1.0. Does NOT use self-reported LLM confidence.
    """
    FALLBACK = "Thank you! The team will reply to you soon."
    if answer.strip() == FALLBACK:
        return 0.0
    # Confidence primarily driven by retrieval quality
    score = min(top_similarity, 1.0)
    return round(score, 4)
