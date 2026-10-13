import math
import random
import uuid
from dataclasses import dataclass

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select
from llama_index.core.prompts import PromptTemplate
from llama_index.llms.openai import OpenAI

from database.models import Source, Chunk
from wiki_search_tool import fetch_wikipedia_pages

load_dotenv("keys.env")


SAMPLE_FRACTION = 0.5        # take about half of each source's chunks
MAX_CHUNKS_PER_SOURCE = 8    # but never more than this from one source
MAX_SMALL_FILE_CHUNKS = 5
MAX_TOTAL_PASSAGES = 24      # one LLM call stays a reasonable size
CARDS_PER_PASSAGE = 2
MIN_CARDS, MAX_CARDS = 3, 40


@dataclass
class Passage:
    label: str   # where it came from: "notes.txt" or "Wikipedia: title"
    text: str


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


def plan_card_count(num_passages: int) -> int:
    return max(MIN_CARDS, min(MAX_CARDS, num_passages * CARDS_PER_PASSAGE))


# ---------- Step 2: generate cards (LLM, no DB) ----------
# These classes are the contract with the LLM. The Field descriptions are sent
# to the model as part of the JSON schema, so they work like extra instructions.
class CardDraft(BaseModel):
    front: str = Field(description="A question or key term. One idea only, under 20 words.")
    back: str = Field(description="The answer in 1-3 sentences, using only the passage.")
    passage: int = Field(description="The number of the passage this card is based on.")


class DeckDraft(BaseModel):
    cards: list[CardDraft]


FLASHCARD_PROMPT = PromptTemplate(
    """You are making study flashcards from the numbered passages below.

Rules:
- Write {num_cards} cards, spread across the passages rather than taken from just one.
- Each card tests ONE fact or idea that its passage states directly. Do not add outside knowledge.
- Prefer important ideas (causes, definitions, key dates, relationships) over minor trivia.
- Ignore citation markers like [12], page furniture, and navigation text.
- No two cards should test the same fact.
- Set `passage` to the number of the passage each card comes from.
- Do not repeat the question in the answer

Passages:
{passages}
"""
)


def format_passages(passages: list[Passage]) -> str:
    return "\n\n".join(f"[{i}] ({p.label})\n{p.text}" for i, p in enumerate(passages, start=1))


@dataclass
class GeneratedCard:
    front: str
    back: str
    source_label: str


def generate_cards(passages: list[Passage], num_cards: int) -> list[GeneratedCard]:
    if not passages:
        raise ValueError("No content to make flashcards from")

    llm = OpenAI(model="gpt-4.1", temperature=0.3)
    # structured_predict fills in the prompt, asks the model for JSON matching
    # DeckDraft, and validates it with Pydantic. We get a DeckDraft object back,
    # not text to parse.
    deck = llm.structured_predict(
        DeckDraft,
        FLASHCARD_PROMPT,
        num_cards=num_cards,
        passages=format_passages(passages),
    )

    
    cards, seen_fronts = [], set()
    for draft in deck.cards:
        front, back = draft.front.strip(), draft.back.strip()
        if not front or not back:
            continue
        if not 1 <= draft.passage <= len(passages):   # cited a passage that doesn't exist
            continue
        if front.lower() in seen_fronts:              # duplicate question
            continue
        seen_fronts.add(front.lower())
        cards.append(GeneratedCard(front=front, back=back,
                                   source_label=passages[draft.passage - 1].label))
    return cards[:num_cards]