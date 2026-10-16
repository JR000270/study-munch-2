# import math
# import random
# import uuid
from dataclasses import dataclass

from dotenv import load_dotenv
from pydantic import BaseModel, Field
# from sqlalchemy import func
# from sqlmodel import Session, select
from llama_index.core.prompts import PromptTemplate
from llama_index.llms.openai import OpenAI

# from database.models import Source, Chunk
# from wiki_search_tool import fetch_wikipedia_pages
from passages import Passage, format_passages, CARDS_PER_PASSAGE


load_dotenv("keys.env")

MIN_CARDS, MAX_CARDS = 3, 40


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

@dataclass
class GeneratedCard:
    front: str
    back: str
    source_label: str


def generate_cards(passages: list[Passage], num_cards: int, callback_manager = None) -> list[GeneratedCard]:
    if not passages:
        raise ValueError("No content to make flashcards from")

    
    llm = OpenAI(model="gpt-4.1", callback_manager=callback_manager, temperature=0.3)
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