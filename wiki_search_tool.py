import httpx
from llama_index.core.tools import FunctionTool

WIKI_API = "https://en.wikipedia.org/w/api.php"
# Wikipedia blocks requests without a descriptive User-Agent
HEADERS = {"User-Agent": "StudyRAGAgent/0.1 (learning project; jadenrandolph@outlook.com)"}
MAX_CHARS = 1500  # per article, to keep the context window under control

class WikiError(Exception):
    """Wikipedia couldn't be reached or returned something unreadable."""
 
 
# both the chat agent's tool and the flashcard generator use it, each formatting the results their own way.
def fetch_wikipedia_pages(query: str, limit: int = 3) -> list[dict]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",   # run a search...
        "gsrsearch": query,
        "gsrlimit": limit,
        "prop": "extracts",      # ...and fetch each result's text in the same request
        "exintro": 1,            # intro section only
        "explaintext": 1,        # plain text, not HTML
        "exlimit": limit,
        "redirects": 1,
    }
    try:
        resp = httpx.get(WIKI_API, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise WikiError(str(e)) from e
 
    pages = data.get("query", {}).get("pages", {})
    # pages is a dict keyed by page ID (unordered); "index" holds the search rank
    ranked = sorted(pages.values(), key=lambda p: p.get("index", 0))
 
    results = []
    for page in ranked:
        extract = page.get("extract", "").strip()
        if not extract:
            continue
        if len(extract) > MAX_CHARS:
            extract = extract[:MAX_CHARS].rsplit(" ", 1)[0] + "..."
        results.append({
            "title": page["title"],
            "url": "https://en.wikipedia.org/wiki/" + page["title"].replace(" ", "_"),
            "extract": extract,
        })
    return results


def make_wiki_search_tool() -> FunctionTool:
    def search_wikipedia(query: str) -> str:
        """Search Wikipedia for background information on a topic.
 
        Use this ONLY when search_notes returns NO_RELEVANT_CONTEXT, or when the
        notes only partially answer the question. Wikipedia uses keyword search,
        so pass a short topic phrase (e.g. "Halloween"), not a full question.
        Results are from Wikipedia, NOT the user's notes, so make that clear
        when using them in an answer.
        """
        try:
            pages = fetch_wikipedia_pages(query)
        except WikiError as e:
            return f"WIKI_ERROR: Could not reach Wikipedia ({e}). Answer from the notes if possible and tell the user Wikipedia was unavailable."
 
        if not pages:
            return "NO_WIKI_RESULTS: Wikipedia had no matching articles. Try a shorter or different keyword."
 
        parts = [
            f"[W{i}] Wikipedia: {p['title']}\n{p['url']}\n{p['extract']}"
            for i, p in enumerate(pages, start=1)
        ]
        return "EXTERNAL SOURCE (Wikipedia, not the user's notes):\n\n" + "\n\n".join(parts)
 
    return FunctionTool.from_defaults(fn=search_wikipedia)