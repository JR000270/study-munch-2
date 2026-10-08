import uuid
from sqlmodel import Session
from llama_index.core.tools import FunctionTool
from tools.db import engine
from tools.chunking import search_chunks

def format_results(results) -> str:
    if not results:
        return "NO_RELEVANT_CONTEXT: The user's notes don't cover this question."
    parts = []
    for i, (chunk, source, distance) in enumerate(results, start=1):
        parts.append(f"[{i}] Source: {source.name} ({source.source_type})\n{chunk.content}")
    return "\n\n".join(parts)

def make_search_tool(topic_id: uuid.UUID) -> FunctionTool:
    def search_notes(query: str) -> str:
        """Search the user's uploaded study notes for passages relevant to the query.

        Use this FIRST for any question about the study topic. Returns numbered
        passages with their source names. Returns NO_RELEVANT_CONTEXT if nothing
        in the notes matches.
        """
        with Session(engine) as session:
            results = search_chunks(session=session, topic_id=topic_id, question=query, k=5)

            # #for distance testing
            # for chunk, source, distance in results:
            #     print(f"[debug] distance={distance:.4f}  {source.name}  {chunk.content[:60]!r}")
            
            return format_results(results)

    return FunctionTool.from_defaults(fn=search_notes)