def format_results(results) -> str:
    if not results:
        return "NO_RELEVANT_CONTEXT: The user's notes don't cover this question."
    parts = []
    for i, (chunk, source, distance) in enumerate(results, start=1):
        parts.append(f"[{i}] Source: {source.name} ({source.source_type})\n{chunk.content}")
    return "\n\n".join(parts)