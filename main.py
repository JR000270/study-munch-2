import uuid
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlmodel import Session, select

from llama_index.core import SimpleDirectoryReader

from db import engine, get_session
from database.models import User, Topic, Source, Chat, Message, FlashcardDeck, Flashcard
from auth import CurrentUser, authenticate_user, create_access_token, hash_password
from chunking import ingest_source
from chat_service import chat_turn

from flashcards import (sample_note_passages, wiki_passages, cap_passages,
                        plan_card_count, generate_cards)
from wiki_search_tool import WikiError

UPLOAD_DIR = Path("uploads")
ALLOWED_EXTENSIONS = {".txt", ".md"}      # start small; PDFs need an extra reader package
MAX_UPLOAD_BYTES = 5 * 1024 * 1024        # 5 MB

app = FastAPI(title="Study RAG Agent")

SessionDep = Annotated[Session, Depends(get_session)]


# ---------- API shapes (separate from the DB tables on purpose) ----------
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)

class UserOut(BaseModel):
    id: uuid.UUID
    username: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)

class TopicOut(BaseModel):
    id: uuid.UUID
    name: str

class SourceOut(BaseModel):
    id: uuid.UUID
    name: str
    source_type: str
    chunk_count: int | None = None

class ChatCreate(BaseModel):
    name: str

class ChatOut(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    name: str

class MessageIn(BaseModel):
    content: str

class MessageOut(BaseModel):
    role: str
    content: str

class DeckCreate(BaseModel):
    name: str
    source_ids: list[uuid.UUID] = []
    include_wikipedia: bool = False
    wiki_query: str | None = None

class CardOut(BaseModel):
    id: uuid.UUID
    front: str
    back: str

class DeckOut(BaseModel):
    id: uuid.UUID
    name: str
    cards: list[CardOut]

class DeckListOut(BaseModel):
    id: uuid.UUID
    name: str
    num_cards: int


# ---------- Ownership checks ----------
# Every topic-scoped endpoint goes through these. They answer 404 (not 403) for
# someone else's data so the API doesn't reveal that the ID exists at all.
def get_owned_topic(session: Session, topic_id: uuid.UUID, user: User) -> Topic:
    topic = session.get(Topic, topic_id)
    if topic is None or topic.user_id != user.id:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


def get_owned_chat(session: Session, chat_id: uuid.UUID, user: User) -> Chat:
    chat = session.get(Chat, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    get_owned_topic(session, chat.topic_id, user)   # a chat belongs to you if its topic does
    return chat

def get_owned_deck(session: Session, deck_id: uuid.UUID, user: User) -> FlashcardDeck:
    deck = session.get(FlashcardDeck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="Deck not found")
    get_owned_topic(session, deck.topic_id, user) 
    return deck


# ---------- Auth ----------
@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(body: UserCreate, session: SessionDep):
    existing = session.exec(select(User).where(User.username == body.username)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    user = User(username=body.username, password_hash=hash_password(body.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        # Two people registering the same name at the same moment can both pass
        # the check above; the DB's unique constraint is the real guarantee.
        session.rollback()
        raise HTTPException(status_code=409, detail="Username already taken")
    return UserOut(id=user.id, username=user.username)


# OAuth2PasswordRequestForm reads form fields named exactly "username" and
# "password" (OAuth2 spec). That's what makes the /docs Authorize button work.
@app.post("/auth/token", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep):
    user = authenticate_user(session, form.username, form.password)
    if user is None:
        # Same message for "no such user" and "wrong password", on purpose.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(user.id))


@app.get("/auth/me", response_model=UserOut)
def me(user: CurrentUser):
    return UserOut(id=user.id, username=user.username)


# ---------- Topics ----------
@app.post("/topics", response_model=TopicOut, status_code=201)
def create_topic(body: TopicCreate, user: CurrentUser, session: SessionDep):
    topic = Topic(user_id=user.id, name=body.name)   # owner comes from the token, never the body
    session.add(topic)
    session.commit()
    return TopicOut(id=topic.id, name=topic.name)


@app.get("/topics", response_model=list[TopicOut])
def list_topics(user: CurrentUser, session: SessionDep):
    topics = session.exec(
        select(Topic).where(Topic.user_id == user.id).order_by(Topic.created_at)
    ).all()
    return [TopicOut(id=t.id, name=t.name) for t in topics]


# ---------- Sources (context files) ----------
# Plain `def`: reading, embedding and DB writes are blocking, so FastAPI runs
# this in a thread pool instead of freezing the event loop.
@app.post("/topics/{topic_id}/sources", response_model=SourceOut, status_code=201)
def upload_source(
    topic_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    file: UploadFile = File(...),
):
    get_owned_topic(session, topic_id, user)

    # Never trust the client's filename for paths: "../../db.py" is a valid filename.
    filename = Path(file.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Allowed types: {sorted(ALLOWED_EXTENSIONS)}")

    data = file.file.read(MAX_UPLOAD_BYTES + 1)   # read one extra byte to detect "too big"
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large")
    if not data:
        raise HTTPException(status_code=400, detail="File is empty")

    source = Source(topic_id=topic_id, name=filename, source_type="upload", storage_path="")
    topic_dir = UPLOAD_DIR / str(topic_id)
    topic_dir.mkdir(parents=True, exist_ok=True)
    path = topic_dir / f"{source.id}{suffix}"
    path.write_bytes(data)
    source.storage_path = str(path)

    try:
        session.add(source)
        session.flush()   # INSERT the source so the chunks' foreign key has a row to point at
        documents = SimpleDirectoryReader(input_files=[str(path)]).load_data()
        count = ingest_source(session=session, source=source, documents=documents)  # commits source + chunks together
    except Exception as e:
        session.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {e}")

    return SourceOut(id=source.id, name=source.name, source_type=source.source_type, chunk_count=count)


@app.get("/topics/{topic_id}/sources", response_model=list[SourceOut])
def list_sources(topic_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    get_owned_topic(session, topic_id, user)
    sources = session.exec(select(Source).where(Source.topic_id == topic_id)).all()
    return [SourceOut(id=s.id, name=s.name, source_type=s.source_type) for s in sources]


# ---------- Chats ----------
@app.post("/topics/{topic_id}/chats", response_model=ChatOut, status_code=201)
def create_chat(topic_id: uuid.UUID, body: ChatCreate, user: CurrentUser, session: SessionDep):
    get_owned_topic(session, topic_id, user)
    chat = Chat(topic_id=topic_id, name=body.name)
    session.add(chat)
    session.commit()
    return ChatOut(id=chat.id, topic_id=chat.topic_id, name=chat.name)


@app.get("/topics/{topic_id}/chats", response_model=list[ChatOut])
def list_chats(topic_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    get_owned_topic(session, topic_id, user)
    chats = session.exec(
        select(Chat).where(Chat.topic_id == topic_id).order_by(Chat.created_at)
    ).all()
    return [ChatOut(id=c.id, topic_id=c.topic_id, name=c.name) for c in chats]


@app.get("/chats/{chat_id}/messages", response_model=list[MessageOut])
def get_messages(chat_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    get_owned_chat(session, chat_id, user)
    rows = session.exec(
        select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at)
    ).all()
    return [MessageOut(role=m.role, content=m.content) for m in rows]


# `async def` because chat_turn is async. No SessionDep here: the ownership
# check uses a short session that closes before the slow LLM call starts.
@app.post("/chats/{chat_id}/messages", response_model=MessageOut)
async def send_message(chat_id: uuid.UUID, body: MessageIn, user: CurrentUser) ->MessageOut: 
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="Message is empty")
    with Session(engine) as session:
        get_owned_chat(session, chat_id, user)
    answer = await chat_turn(chat_id, body.content)
    return MessageOut(role="assistant", content=answer)

# --- Flashcards ---
@app.post("/topics/{topic_id}/decks", status_code=201, response_model=DeckOut)
def create_deck(topic_id: uuid.UUID, body: DeckCreate, user: CurrentUser):
    if not body.source_ids and not body.include_wikipedia:
        raise HTTPException(status_code=400, detail="Pick at least one source or enable Wikipedia")
    #open a session to check the topic is yours
    with Session(engine) as session:
        topic = get_owned_topic(session, topic_id, user)
        topic_name = topic.name

        #check every source_id the user chose that also belongs to this topic, then sample passages.
        sources = session.exec(
            select(Source).where(Source.id.in_(body.source_ids), Source.topic_id == topic_id)
        ).all()
        if len(sources) != len(set(body.source_ids)):
                    raise HTTPException(status_code=404, detail="Source not found")
        
        passages = sample_note_passages(session, [s.id for s in sources])


    #if include_wikipedia: add wiki passages (default query = topic name).
    if body.include_wikipedia:
        try:
            passages += wiki_passages(body.wiki_query or topic_name)
        except WikiError as e:
            print(f"(Wikipedia unavailable, continuing without it: {e})")

    if not passages:
        raise HTTPException(status_code=400, detail="No content found to make flashcards from")        
    
    #cap passages, plan the card count, generate cards.
    passages = cap_passages(passages)
    num_cards = plan_card_count(len(passages))
    cards = generate_cards(passages, num_cards)
    
    #make a new session: save a FlashcardDeck, then one Flashcard per card
    #    (front -> title, back -> content). Commit.
    with Session(engine) as session:
        deck = FlashcardDeck(topic_id=topic_id, name=body.name)
        session.add(deck)
        session.flush()
        flashcards = [Flashcard(deck_id=deck.id, title=c.front, content=c.back) for c in cards]
        session.add_all(flashcards)
        output_deck = DeckOut(
            id=deck.id,
            name=deck.name,
            cards=[CardOut(id=f.id, front=f.title, back=f.content) for f in flashcards], #turns the cards into database object with id's
        )
        session.commit()
    #returns the deck id, name, and the cards
    return output_deck


#just gets the deck id, name, card count
@app.get("/topics/{topic_id}/decks", response_model=list[DeckListOut])
def list_decks(topic_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    get_owned_topic(session, topic_id, user)
    decks = session.exec(
        select(FlashcardDeck).where(FlashcardDeck.topic_id == topic_id).order_by(FlashcardDeck.created_at)
    ).all()

    deck_ids = [d.id for d in decks]
    card_counts = {}

    rows = session.exec(
        select(Flashcard.deck_id, func.count())
        .where(Flashcard.deck_id.in_(deck_ids))
        .group_by(Flashcard.deck_id)
    ).all()
    card_counts = {deck_id: count for deck_id, count in rows}

    return [DeckListOut(id=d.id, name=d.name, num_cards=card_counts.get(d.id, 0)) for d in decks]

#get the cards from a given deck
@app.get("/decks/{deck_id}/cards", response_model=list[CardOut])
def list_deck_cards(deck_id: uuid.UUID, user:CurrentUser, session: SessionDep):
    get_owned_deck(session, deck_id, user)
    cards = session.exec(
        select(Flashcard).where(Flashcard.deck_id == deck_id)
    ).all()
    return [CardOut(id=c.id, front=c.title, back=c.content) for c in cards]