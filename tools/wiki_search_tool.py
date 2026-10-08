import httpx
from llama_index.core.tools import FunctionTool

WIKI_API = "https://en.wikipedia.org/w/api.php"
# Wikipedia blocks requests without a descriptive User-Agent
HEADERS = {"User-Agent": "StudyRAGAgent/0.1 (learning project; jadenrandolph@outlook.com)"}
MAX_CHARS = 1500  # per article, to keep the context window under control


def make_wiki_search_tool() -> FunctionTool:
    def search_wikipedia(query: str) -> str:
        """Search Wikipedia for background information on a topic.

        Use this ONLY when search_notes returns NO_RELEVANT_CONTEXT, or when the
        notes only partially answer the question. Wikipedia uses keyword search,
        so pass a short topic phrase (e.g. "Halloween"), not a full question.
        Results are from Wikipedia, NOT the user's notes, so make that clear
        when using them in an answer.
        """
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",   # run a search...
            "gsrsearch": query,
            "gsrlimit": 3,
            "prop": "extracts",      # ...and fetch each result's text in the same request
            "exintro": 1,            # intro section only
            "explaintext": 1,        # plain text, not HTML
            "exlimit": 3,
            "redirects": 1,
        }
        try:
            resp = httpx.get(WIKI_API, params=params, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            return f"WIKI_ERROR: Could not reach Wikipedia ({e}). Answer from the notes if possible and tell the user Wikipedia was unavailable."

        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return "NO_WIKI_RESULTS: Wikipedia had no matching articles. Try a shorter or different keyword."

        # pages is a dict keyed by page ID (unordered); "index" holds the search rank
        ranked = sorted(pages.values(), key=lambda p: p.get("index", 0))

        parts = []
        for i, page in enumerate(ranked, start=1):
            extract = page.get("extract", "").strip()
            if not extract:
                continue
            if len(extract) > MAX_CHARS:
                extract = extract[:MAX_CHARS].rsplit(" ", 1)[0] + "..."
            url = "https://en.wikipedia.org/wiki/" + page["title"].replace(" ", "_")
            parts.append(f"[W{i}] Wikipedia: {page['title']}\n{url}\n{extract}")

        if not parts:
            return "NO_WIKI_RESULTS: Matching articles had no usable text."
        return "EXTERNAL SOURCE (Wikipedia, not the user's notes):\n\n" + "\n\n".join(parts)

    return FunctionTool.from_defaults(fn=search_wikipedia)