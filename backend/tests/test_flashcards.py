import sys
from sqlmodel import Session, select

from db import engine
from database.models import User, Topic, Source
from backend.tools.passages import sample_note_passages, wiki_passages, cap_passages
from backend.services.flashcards import plan_card_count, generate_cards
from backend.tools.wiki_search_tool import WikiError

# usage: python test_flashcards.py <username> "<topic name>" [wiki query]
# Generates cards and prints them. Nothing is saved to the database.
username, topic_name = sys.argv[1], sys.argv[2]
wiki_query = sys.argv[3] if len(sys.argv) > 3 else None

# --- DB work in a short session ---
with Session(engine) as session:
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise SystemExit(f"No user named {username}")
    topic = session.exec(
        select(Topic).where(Topic.user_id == user.id, Topic.name == topic_name)
    ).first()
    if topic is None:
        raise SystemExit(f"{username} has no topic named {topic_name!r}")
    sources = session.exec(select(Source).where(Source.topic_id == topic.id)).all()
    print(f"Sources: {[s.name for s in sources]}")
    passages = sample_note_passages(session, [s.id for s in sources])

# --- Network work with no session open ---
if wiki_query:
    try:
        passages += wiki_passages(wiki_query)
    except WikiError as e:
        print(f"(Wikipedia unavailable, continuing without it: {e})")

passages = cap_passages(passages)
num_cards = plan_card_count(len(passages))
print(f"{len(passages)} passages -> asking for {num_cards} cards\n")
for i, p in enumerate(passages, start=1):
    print(f"  [{i}] {p.label}: {p.text[:70]!r}...")

cards = generate_cards(passages, num_cards)
print(f"\nGot {len(cards)} cards:\n")
for i, card in enumerate(cards, start=1):
    print(f"{i}. Q: {card.front}\n   A: {card.back}\n   ({card.source_label})\n")