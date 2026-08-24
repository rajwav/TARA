import subprocess
import urllib.parse
import logging
from tara.security import security_guard, RiskLevel

logger = logging.getLogger("tara.actions.browser")


def open_browser_url(url: str) -> str:
    """Safely open a validated URL in the default macOS web browser."""
    if not url or not url.strip():
        return "Error: URL cannot be empty."

    clean_url = url.strip()
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        clean_url = f"https://{clean_url}"

    try:
        result = subprocess.run(["open", clean_url], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            security_guard.log_action("open_browser_url", {"url": clean_url}, RiskLevel.LOW, "success")
            return f"Successfully opened `{clean_url}` in default browser."
        else:
            security_guard.log_action("open_browser_url", {"url": clean_url}, RiskLevel.LOW, "failed")
            return f"Failed to open browser URL '{clean_url}': {result.stderr.strip()}"

    except Exception as e:
        security_guard.log_action("open_browser_url", {"url": clean_url}, RiskLevel.LOW, "failed")
        return f"Error opening URL '{clean_url}': {e}"


def web_search(query: str) -> str:
    """Perform a web search using DuckDuckGo API with structured results."""
    if not query or not query.strip():
        return "Error: Search query cannot be empty."

    clean_query = query.strip()
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(clean_query, max_results=5))

        if not results:
            security_guard.log_action("web_search", {"query": clean_query}, RiskLevel.LOW, "no_results")
            return f"No web search results found for '{clean_query}'."

        output = [f"**Web Search Results for '{clean_query}':**\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "No Title")
            snippet = r.get("body", "")
            href = r.get("href", "")
            output.append(f"{i}. **{title}**\n   {snippet}\n   *Source:* {href}\n")

        security_guard.log_action("web_search", {"query": clean_query, "count": len(results)}, RiskLevel.LOW, "success")
        return "\n".join(output)

    except Exception as e:
        logger.warning(f"DuckDuckGo API search failed: {e}. Falling back to browser search.")
        encoded = urllib.parse.quote_plus(clean_query)
        search_url = f"https://duckduckgo.com/?q={encoded}"
        open_browser_url(search_url)
        security_guard.log_action("web_search", {"query": clean_query, "fallback": "browser"}, RiskLevel.LOW, "fallback_opened")
        return f"Opened web search for '{clean_query}' in your browser."
