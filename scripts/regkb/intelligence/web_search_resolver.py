"""
Web-search fallback for LinkedIn/social URLs in the IMAP reply pipeline.

When url_resolver marks an entry as `needs_manual` (typically LinkedIn posts
behind a login wall), this module uses an LLM tool-calling loop to search the
web for the actual regulatory guidance document URL.

Architecture:
  1. LLM receives the entry title + agency and a `web_search` tool
  2. LLM decides what to search for, calls the tool
  3. Tool executes via duckduckgo-search (no API key needed)
  4. LLM evaluates results, optionally refines the query
  5. Returns the best URL on a trusted regulatory domain, or None

Reuses the same Ollama tool-calling pattern as agents/regkb_query.
"""

import json
import logging
from typing import Optional

import httpx
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definition (Ollama-compatible schema)
# ---------------------------------------------------------------------------

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for regulatory guidance documents.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to find the official document",
                },
            },
            "required": ["query"],
        },
    },
}

# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Execute a DuckDuckGo web search. Returns [{title, url, snippet}]."""
    try:
        results = DDGS().text(query, max_results=max_results)
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]
    except Exception as exc:
        logger.warning(f"DuckDuckGo search failed: {exc}")
        return []


TOOL_DISPATCH = {"web_search": web_search}

# ---------------------------------------------------------------------------
# Ollama chat helper (mirrors regkb_query/agent.py pattern)
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "qwen3.5:4b"
OLLAMA_BASE_URL = "http://127.0.0.1:11434"


def _call_ollama(
    messages: list[dict],
    tools: list[dict],
    model: str,
    base_url: str,
) -> dict:
    """Single /api/chat call. Returns the assistant message dict."""
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "options": {"temperature": 0.1, "num_predict": 512},
        "think": False,
        "stream": False,
        "keep_alive": "5m",
    }
    resp = httpx.post(f"{base_url}/api/chat", json=payload, timeout=120.0)
    resp.raise_for_status()
    return resp.json().get("message", {}) or {}


def _execute_tool_call(tc: dict) -> str:
    """Dispatch one tool_call to its Python function."""
    fn_name = tc.get("function", {}).get("name", "")
    args = tc.get("function", {}).get("arguments", {}) or {}
    if fn_name not in TOOL_DISPATCH:
        return json.dumps({"error": f"unknown tool: {fn_name}"})
    try:
        result = TOOL_DISPATCH[fn_name](**args)
        return json.dumps(result, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Domain validation
# ---------------------------------------------------------------------------


def _is_on_trusted_domain(url: str, trusted_domains: list[str]) -> bool:
    """Check if a URL belongs to one of the trusted regulatory domains."""
    from urllib.parse import urlparse

    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return any(td in domain for td in trusted_domains)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a regulatory document finder. Given a document title and agency, "
    "search the web to find the official guidance document URL.\n\n"
    "Rules:\n"
    "- Use the web_search tool to find the document\n"
    "- Only return URLs from trusted regulatory domains: {domains}\n"
    "- If the first search doesn't find a good match, try a different query "
    "(e.g., add 'guidance', use agency acronym, add 'filetype:pdf')\n"
    "- When you find the right URL, respond with JUST the URL on its own line, "
    "nothing else\n"
    "- If you cannot find it after searching, respond with 'NOT_FOUND'"
)


def web_search_resolve(
    title: str,
    agency: str,
    trusted_domains: list[str],
    model: str = DEFAULT_MODEL,
    ollama_base_url: str = OLLAMA_BASE_URL,
    max_turns: int = 3,
) -> Optional[str]:
    """Search the web for a regulatory document URL using LLM tool-calling.

    Args:
        title: Document title from the digest entry.
        agency: Issuing regulatory agency.
        trusted_domains: List of domain strings the returned URL must match.
        model: Ollama model name.
        ollama_base_url: Ollama API base URL.
        max_turns: Maximum LLM round-trips.

    Returns:
        A URL string on a trusted domain, or None if not found.
    """
    system = SYSTEM_PROMPT.format(domains=", ".join(trusted_domains))
    user_msg = f"Find the official document: '{title}' from {agency}"

    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]
    tools = [SEARCH_TOOL]

    try:
        for _turn in range(max_turns):
            msg = _call_ollama(messages, tools, model, ollama_base_url)
            tool_calls = msg.get("tool_calls", []) or []

            if not tool_calls:
                # LLM produced a final answer — extract URL or NOT_FOUND
                content = (msg.get("content") or "").strip()
                if "NOT_FOUND" in content.upper():
                    logger.info(f"Web search: LLM could not find '{title}'")
                    return None

                # Try to extract a URL from the response
                url = _extract_url(content)
                if url and _is_on_trusted_domain(url, trusted_domains):
                    logger.info(f"Web search resolved '{title}' -> {url}")
                    return url

                logger.info(f"Web search: LLM response not a trusted URL: {content[:200]}")
                return None

            # Execute tool calls, feed results back
            messages.append({"role": "assistant", "content": "", "tool_calls": tool_calls})
            for tc in tool_calls:
                output = _execute_tool_call(tc)
                messages.append({"role": "tool", "content": output})

        # Exhausted turns
        logger.info(f"Web search: max turns reached for '{title}'")
        return None

    except httpx.HTTPError as exc:
        logger.warning(f"Web search HTTP error: {exc}")
        return None
    except Exception as exc:
        logger.warning(f"Web search error: {exc}")
        return None


def _extract_url(text: str) -> Optional[str]:
    """Extract the first HTTP(S) URL from text."""
    import re

    match = re.search(r"https?://[^\s<>\"')\]]+", text)
    return match.group(0).rstrip(".,;:") if match else None
