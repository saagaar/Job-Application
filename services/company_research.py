from __future__ import annotations


def research_company(company: str, max_results: int = 3) -> str:
    """Return a plain-text summary of a company scraped from DuckDuckGo.

    Uses two targeted queries — general overview + engineering/culture — and
    combines the top snippets. Returns an empty string on any failure so the
    cover letter generation still works without company context.
    """
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
    except ImportError:
        return ""

    queries = [
        f"{company} company about mission product what they do",
        f"{company} engineering culture values team",
    ]

    snippets: list[str] = []
    try:
        with DDGS() as ddgs:
            for query in queries:
                for r in ddgs.text(query, max_results=max_results):
                    title = r.get("title", "").strip()
                    body  = r.get("body", "").strip()
                    if body:
                        snippets.append(f"[{title}]\n{body}")
                    if len(snippets) >= max_results * 2:
                        break
    except Exception:
        return ""

    return "\n\n".join(snippets)
