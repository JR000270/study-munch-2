from dataclasses import dataclass
from database.models import Source, Chunk
from wiki_search_tool import fetch_wikipedia_pages
from sqlmodel import Session, select
from sqlalchemy import func
from dotenv import load_dotenv
from wiki_search_tool import WikiError
from fastapi import HTTPException

from database.models import User, Topic
from db import engine
import math
import random
import uuid

SAMPLE_FRACTION = 0.5        # take about half of each source's chunks
MAX_CHUNKS_PER_SOURCE = 8    # but never more than this from one source
MAX_SMALL_FILE_CHUNKS = 5
MAX_TOTAL_PASSAGES = 24      # one LLM call stays a reasonable size
CARDS_PER_PASSAGE = 2

load_dotenv("keys.env")

@dataclass
class Passage:
    label: str   # where it came from: "notes.txt" or "Wikipedia: title"
    text: str

def get_owned_topic(session: Session, topic_id: uuid.UUID, user: User) -> Topic:
    topic = session.get(Topic, topic_id)
    if topic is None or topic.user_id != user.id:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


# ---------- Step 1: gather passages (DB and Wikipedia, no LLM) ----------
def sample_note_passages(session: Session, source_ids: list[uuid.UUID]) -> list[Passage]:
    """Random chunks from each source, more from sources that have more content."""
    passages = []
    for source_id in source_ids:
        source = session.get(Source, source_id)
        total = session.exec(
            select(func.count()).select_from(Chunk).where(Chunk.source_id == source_id)
        ).one()
        if source is None or total == 0:
            continue
        if total < MAX_SMALL_FILE_CHUNKS:
            k = total
        else:
            k = min(total, MAX_CHUNKS_PER_SOURCE, max(1, math.ceil(total * SAMPLE_FRACTION)))
        chunks = session.exec(
            select(Chunk)
            .where(Chunk.source_id == source_id)
            .order_by(func.random())   # Postgres shuffles; we take the first k
            .limit(k)
        ).all()
        # Back into document order, so the LLM reads them the way the notes flow
        for chunk in sorted(chunks, key=lambda c: c.chunk_index):
            passages.append(Passage(label=source.name, text=chunk.content))
    return passages


def wiki_passages(query: str) -> list[Passage]:
    """Each article intro becomes one passage. Raises WikiError if Wikipedia is down."""
    return [
        Passage(label=f"Wikipedia: {p['title']}", text=p["extract"])
        for p in fetch_wikipedia_pages(query)
    ]


def cap_passages(passages: list[Passage]) -> list[Passage]:
    if len(passages) <= MAX_TOTAL_PASSAGES:
        return passages
    keep = sorted(random.sample(range(len(passages)), MAX_TOTAL_PASSAGES))  # keep original order
    return [passages[i] for i in keep]

def format_passages(passages: list[Passage]) -> str:
    return "\n\n".join(f"[{i}] ({p.label})\n{p.text}" for i, p in enumerate(passages, start=1))

def gather_passages(topic_id: uuid.UUID, user: User, source_ids: list[uuid.UUID],
                    include_wikipedia: bool, wiki_query: str | None) -> list[Passage]:
    if not source_ids and not include_wikipedia:
        raise HTTPException(status_code=400, detail="Pick at least one source or enable Wikipedia")

    with Session(engine) as session:
        topic = get_owned_topic(session, topic_id, user)
        topic_name = topic.name
        sources = session.exec(
            select(Source).where(Source.id.in_(source_ids), Source.topic_id == topic_id)
        ).all()
        if len(sources) != len(set(source_ids)):
            raise HTTPException(status_code=404, detail="Source not found")
        passages = sample_note_passages(session, [s.id for s in sources])

    if include_wikipedia:
        try:
            passages += wiki_passages(wiki_query or topic_name)
        except WikiError as e:
            print(f"(Wikipedia unavailable, continuing without it: {e})")

    if not passages:
        raise HTTPException(status_code=400, detail="No content found to make questions from")
    return cap_passages(passages)