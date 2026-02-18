"""
LLM-powered question answering for Telegram bot.

Routing strategy:
- Simple/factual queries → local Nexa/Qwen on NPU (fast, free)
- Complex/analytical queries → Claude Haiku via API (smarter, ~$0.01/query)
- Fallback → KB search if neither LLM is available

The local LLM server (Nexa SDK) must be running at the configured endpoint.
Claude requires ANTHROPIC_API_KEY in environment.
"""

import asyncio
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Nexa SDK local server config
NEXA_ENDPOINT = "http://127.0.0.1:18181/v1/chat/completions"
NEXA_MODEL = "NexaAI/Qwen3-4B-Instruct-2507-npu"
NEXA_TIMEOUT = 30

# Claude Haiku config
CLAUDE_MODEL = "claude-3-5-haiku-latest"

# System prompt for KB Q&A
KB_SYSTEM_PROMPT = """You are a regulatory affairs assistant for medical device professionals.
You answer questions based on the search results provided from a regulatory knowledge base.
Be concise (2-4 sentences). Cite document titles when referencing specific documents.
If the search results don't contain the answer, say so honestly.
Do not make up regulatory information — accuracy is critical in this domain."""

# Heuristic for query complexity
COMPLEX_INDICATORS = [
    "compare",
    "difference between",
    "summarize",
    "explain",
    "analyze",
    "implications",
    "recommend",
    "should we",
    "how does",
    "what are the requirements",
    "pros and cons",
]


def is_complex_query(question: str) -> bool:
    """Determine if a question needs Claude (complex) or can use local LLM (simple)."""
    lower = question.lower()
    return any(indicator in lower for indicator in COMPLEX_INDICATORS)


async def answer_question(question: str) -> str:
    """Answer a natural language question about the KB.

    1. Search KB for relevant documents
    2. Build context from search results
    3. Route to local LLM or Claude based on complexity
    4. Return formatted answer

    Args:
        question: Natural language question.

    Returns:
        Answer string ready for Telegram display.
    """
    # Step 1: Search KB for context
    search_results = await asyncio.to_thread(_search_kb, question)

    if not search_results:
        return f'I couldn\'t find any documents matching your question: "{question}"\nTry /search with different keywords.'

    # Build context from search results
    context = _build_context(search_results)

    # Step 2: Route to appropriate LLM
    if is_complex_query(question):
        answer = await _ask_claude(question, context)
        if answer:
            return _format_answer(answer, search_results, "Claude")
    else:
        answer = await _ask_nexa(question, context)
        if answer:
            return _format_answer(answer, search_results, "Local LLM")

    # Fallback: try the other LLM
    if is_complex_query(question):
        answer = await _ask_nexa(question, context)
    else:
        answer = await _ask_claude(question, context)

    if answer:
        return _format_answer(answer, search_results, "LLM")

    # Final fallback: just return search results
    return _format_search_fallback(search_results, question)


def _search_kb(question: str, limit: int = 5) -> list[dict]:
    """Search KB for documents relevant to the question."""
    from regkb.telegram.search_handler import parse_query

    parsed = parse_query(question)

    from regkb.search import SearchEngine

    engine = SearchEngine()
    results = engine.search(
        parsed["query"],
        limit=limit,
        jurisdiction=parsed["jurisdiction"],
        document_type=parsed["document_type"],
    )

    # If filtered search returned nothing, try unfiltered
    if not results and (parsed["jurisdiction"] or parsed["document_type"]):
        results = engine.search(question, limit=limit)

    return results


def _build_context(results: list[dict]) -> str:
    """Build LLM context from search results."""
    parts = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "Untitled")
        jurisdiction = r.get("jurisdiction", "")
        doc_type = r.get("document_type", "")
        excerpt = r.get("excerpt", "")[:300]

        parts.append(f"[{i}] {title} ({jurisdiction}, {doc_type})")
        if excerpt:
            parts.append(f"    Excerpt: {excerpt}")
    return "\n".join(parts)


async def _ask_nexa(question: str, context: str) -> Optional[str]:
    """Ask the local Nexa/Qwen LLM via OpenAI-compatible API."""
    try:
        payload = {
            "model": NEXA_MODEL,
            "messages": [
                {"role": "system", "content": KB_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Based on these documents from our regulatory knowledge base:\n\n{context}\n\nQuestion: {question}",
                },
            ],
            "max_tokens": 300,
            "temperature": 0.3,
        }

        response = await asyncio.to_thread(
            requests.post,
            NEXA_ENDPOINT,
            json=payload,
            timeout=NEXA_TIMEOUT,
        )

        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            # Strip Qwen thinking tags if present
            if "</think>" in content:
                content = content.split("</think>")[-1].strip()
            return content
        else:
            logger.warning("Nexa returned %d: %s", response.status_code, response.text[:200])
            return None

    except requests.ConnectionError:
        logger.debug("Nexa server not running at %s", NEXA_ENDPOINT)
        return None
    except requests.Timeout:
        logger.warning("Nexa request timed out after %ds", NEXA_TIMEOUT)
        return None
    except Exception:
        logger.exception("Nexa LLM request failed")
        return None


async def _ask_claude(question: str, context: str) -> Optional[str]:
    """Ask Claude Haiku via Anthropic API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.debug("ANTHROPIC_API_KEY not set — Claude unavailable")
        return None

    try:
        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 300,
            "system": KB_SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": f"Based on these documents from our regulatory knowledge base:\n\n{context}\n\nQuestion: {question}",
                }
            ],
        }

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        response = await asyncio.to_thread(
            requests.post,
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            return data["content"][0]["text"]
        else:
            logger.warning("Claude returned %d: %s", response.status_code, response.text[:200])
            return None

    except Exception:
        logger.exception("Claude API request failed")
        return None


def _format_answer(answer: str, results: list[dict], source: str) -> str:
    """Format LLM answer with source citations."""
    parts = [answer, ""]

    # Add source documents
    titles = [r.get("title", "Untitled")[:60] for r in results[:3]]
    if titles:
        parts.append("📚 Based on:")
        for title in titles:
            parts.append(f"  • {title}")

    parts.append(f"\n💡 Answered via {source}")
    return "\n".join(parts)


def _format_search_fallback(results: list[dict], question: str) -> str:
    """Format search results as fallback when no LLM is available."""
    parts = [
        f'I found {len(results)} relevant document(s) for: "{question}"\n',
        "(No LLM available for Q&A — showing search results)\n",
    ]

    for i, r in enumerate(results[:5], 1):
        title = r.get("title", "Untitled")
        jurisdiction = r.get("jurisdiction", "")
        parts.append(f"{i}. {title} ({jurisdiction})")

    parts.append("\nUse /search for more details.")
    return "\n".join(parts)
