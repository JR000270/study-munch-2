import uuid
from pathlib import Path
from typing import Annotated
from collections import defaultdict

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlmodel import Session, select

# from llama_index.core import SimpleDirectoryReader

from db import engine, get_session
from database.models import User, Topic, Source, Chat, Message, FlashcardDeck, Flashcard, Quiz, Question, Answer, Attempt, AttemptAnswer
from auth import CurrentUser, authenticate_user, create_access_token, hash_password
from chunking import ingest_source
from chat_service import chat_turn
from flashcards import plan_card_count, generate_cards
from quizzes import generate_quiz, plan_question_count
from passages import  cap_passages, gather_passages
from file_readers import load_documents, SUPPORTED_EXTENSIONS


from datetime import datetime


UPLOAD_DIR = Path("uploads")
ALLOWED_EXTENSIONS = SUPPORTED_EXTENSIONS
MAX_UPLOAD_BYTES = 25 * 1024 * 1024   # 25 MB

app = FastAPI(title="Study Munch")

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


# --- Quiz shapes ---
class QuizCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_ids: list[uuid.UUID] = []
    include_wikipedia: bool = False
    wiki_query: str | None = None
    num_questions: int | None = Field(default=None, ge=1, le=20)   # optional; plan_question_count clamps it anyway

class OptionOut(BaseModel):          # an Answer row, minus is_correct
    id: uuid.UUID
    text: str

class QuestionOut(BaseModel):
    id: uuid.UUID
    question: str
    options: list[OptionOut]

class QuizOut(BaseModel):
    id: uuid.UUID
    name: str
    questions: list[QuestionOut]

class QuizListOut(BaseModel):
    id: uuid.UUID
    name: str
    num_questions: int

class SubmittedAnswer(BaseModel):
    question_id: uuid.UUID
    answer_id: uuid.UUID

class AttemptIn(BaseModel):
    answers: list[SubmittedAnswer]

class QuestionResult(BaseModel):
    question_id: uuid.UUID
    chosen_answer_id: uuid.UUID | None   # None = left blank
    correct_answer_id: uuid.UUID
    is_correct: bool

class AttemptOut(BaseModel):
    id: uuid.UUID
    score: int
    total: int
    results: list[QuestionResult]

class ReviewOption(BaseModel):
    id: uuid.UUID
    text: str
    is_correct: bool
    chosen: bool

class ReviewQuestion(BaseModel):
    id: uuid.UUID
    question: str
    is_correct: bool          # did the user get this question right
    options: list[ReviewOption]

class AttemptReviewOut(BaseModel):
    id: uuid.UUID
    quiz_id: uuid.UUID
    quiz_name: str
    score: int
    total: int
    created_at: datetime
    questions: list[ReviewQuestion]

class AttemptListOut(BaseModel):
    id: uuid.UUID
    score: int
    total: int
    created_at: datetime

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

def get_owned_quiz(session: Session, quiz_id: uuid.UUID, user: User) -> Quiz:
    quiz = session.get(Quiz, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    get_owned_topic(session, quiz.topic_id, user) 
    return quiz

def get_owned_attempt(session, attempt_id, user)->list[AttemptListOut]:
    attempt = session.get(Attempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Quiz Attempt now found")
    get_owned_quiz(session, attempt.quiz_id,user)
    return attempt

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

    # try:
    #     session.add(source)
    #     session.flush()   # INSERT the source so the chunks' foreign key has a row to point at
    #     documents = load_documents(str(path)) #new reader that has the custom ones added to it
    #     #documents = SimpleDirectoryReader(input_files=[str(path)]).load_data()
        
    #     count = ingest_source(session=session, source=source, documents=documents)  # commits source + chunks together
    # except Exception as e:
    #     session.rollback()
    #     path.unlink(missing_ok=True)
    #     if not any(d.text.strip() for d in documents):
    #         path.unlink(missing_ok=True)
    #         raise HTTPException(
    #             status_code=422,
    #             detail="No readable text found. If this is a scanned PDF, it needs OCR first.",
    #         )
    #     else:
    #         raise HTTPException(status_code=500, detail=f"Failed to process file: {e}")
    # --- Phase 1: parse the file. No DB involved, so no rollback needed. ---
    try:
        documents = load_documents(str(path))
    except Exception as e:
        path.unlink(missing_ok=True)
        # A file that can't be parsed is the user's problem (4xx), not the server's
        raise HTTPException(
            status_code=422,
            detail="Could not read this file. It may be corrupted or password-protected.",
        ) from e

    if not documents:   # load_documents already dropped the empty pages
        path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail="No readable text found. If this is a scanned PDF, it needs OCR first.",
        )

    # --- Phase 2: save + embed. This touches the DB, so roll back on failure. ---
    try:
        session.add(source)
        session.flush()
        count = ingest_source(session=session, source=source, documents=documents)
    except Exception as e:
        session.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Failed to process file") from e

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
    passages = gather_passages(topic_id, user, body.source_ids, body.include_wikipedia, body.wiki_query) #calls helper from passages to get the context for the creation of an object like flashcards/quizzes
   
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


#----quizzes section-----
@app.post("/topics/{topic_id}/quizzes", status_code=201, response_model=QuizOut)
def create_quiz(topic_id: uuid.UUID, body: QuizCreate, user: CurrentUser):
    passages = gather_passages(topic_id, user, body.source_ids,
                               body.include_wikipedia, body.wiki_query)
    num_questions = plan_question_count(len(passages), body.num_questions)
    generated = generate_quiz(passages, num_questions)   # slow LLM call, no session open
    if not generated:
        raise HTTPException(status_code=502, detail="Quiz generation failed, please try again")

    with Session(engine) as session:
        quiz = Quiz(topic_id=topic_id, name=body.name)
        session.add(quiz)
        session.flush() #sends out quizzes row to the database to not cause a key error bc of it not being there when it tries to add

        rows = []   # (Question, [Answer, ...]) pairs, kept so we can build the response
        for pos, g in enumerate(generated):
            q = Question(quiz_id=quiz.id, question=g.question, position=pos)
            answers = [
                Answer(question_id=q.id, answer=text, is_correct=(i == g.correct_index), position=i)
                for i, text in enumerate(g.options)
            ]
            rows.append((q, answers))
        session.add_all([q for q, _ in rows])
        session.flush()  #make the questions rows exist 
        session.add_all([a for _, answers in rows for a in answers])

        output = QuizOut(
            id=quiz.id,
            name=quiz.name,
            questions=[
                QuestionOut(id=q.id, question=q.question,
                            options=[OptionOut(id=a.id, text=a.answer) for a in answers])
                for q, answers in rows
            ],
        )
        session.commit()
    return output


@app.get("/quizzes/{quiz_id}", response_model=QuizOut)
def get_quiz(quiz_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    quiz = get_owned_quiz(session, quiz_id, user)
    questions = session.exec(
        select(Question).where(Question.quiz_id == quiz_id).order_by(Question.position)
    ).all()
    answers = session.exec(
        select(Answer)
        .where(Answer.question_id.in_([q.id for q in questions]))
        .order_by(Answer.position)
    ).all()

    options_by_question = defaultdict(list)
    for a in answers:
        options_by_question[a.question_id].append(OptionOut(id=a.id, text=a.answer))

    return QuizOut(
        id=quiz.id,
        name=quiz.name,
        questions=[QuestionOut(id=q.id, question=q.question, options=options_by_question[q.id])
                   for q in questions],
    )

@app.get("/topics/{topic_id}/quizzes")
def get_quiz_list(topic_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> list[QuizListOut]:
    get_owned_topic(session, topic_id, user)
    quizzes = session.exec(
        select(Quiz).where(Quiz.topic_id == topic_id).order_by(Quiz.created_at)
    ).all()

    quiz_ids = [q.id for q in quizzes]
    question_counts = {}

    rows = session.exec(
        select(Question.quiz_id, func.count())
        .where(Question.quiz_id.in_(quiz_ids))
        .group_by(Question.quiz_id)
    ).all()
    question_counts = {quiz_id: count for quiz_id, count in rows}

    return [QuizListOut(id=q.id, name=q.name, num_questions=question_counts.get(q.id, 0)) for q in quizzes]    



@app.post("/quizzes/{quiz_id}/attempts", status_code=201, response_model=AttemptOut)
def submit_attempt(quiz_id: uuid.UUID, body: AttemptIn, user: CurrentUser, session: SessionDep):
    get_owned_quiz(session, quiz_id, user)

    questions = session.exec(
        select(Question).where(Question.quiz_id == quiz_id).order_by(Question.position)
    ).all()
    question_ids = {q.id for q in questions}

    # 1. Every submitted question must belong to THIS quiz, and appear only once
    submitted: dict[uuid.UUID, uuid.UUID] = {}
    for s in body.answers:
        if s.question_id not in question_ids:
            raise HTTPException(status_code=400, detail="Question is not part of this quiz")
        if s.question_id in submitted:
            raise HTTPException(status_code=400, detail="Question answered more than once")
        submitted[s.question_id] = s.answer_id

    answers = session.exec(select(Answer).where(Answer.question_id.in_(question_ids))).all()
    answer_by_id = {a.id: a for a in answers}
    correct_by_question = {a.question_id: a.id for a in answers if a.is_correct}

    # 2. Grade, one result per question (unanswered counts as wrong)
    attempt = Attempt(quiz_id=quiz_id, score=0)
    session.add(attempt)
    session.flush()

    results, score = [], 0
    for q in questions:
        chosen = submitted.get(q.id)
        if chosen is not None:
            picked = answer_by_id.get(chosen)
            if picked is None or picked.question_id != q.id:   # 3. the answer must belong to THIS question
                raise HTTPException(status_code=400, detail="Answer does not match its question")
            session.add(AttemptAnswer(attempt_id=attempt.id, question_id=q.id, answer_id=chosen))

        correct_id = correct_by_question[q.id]
        is_correct = chosen == correct_id
        score += is_correct
        results.append(QuestionResult(question_id=q.id, chosen_answer_id=chosen,
                                      correct_answer_id=correct_id, is_correct=is_correct))

    attempt.score = score
    output = AttemptOut(id=attempt.id, score=score, total=len(questions), results=results)
    session.commit()
    return output

@app.get("/attempts/{attempt_id}", response_model=AttemptReviewOut)
def get_attempt(attempt_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    attempt = get_owned_attempt(session, attempt_id, user)
    quiz = session.get(Quiz, attempt.quiz_id)

    questions = session.exec(
        select(Question).where(Question.quiz_id == quiz.id).order_by(Question.position)
    ).all()
    answers = session.exec(
        select(Answer)
        .where(Answer.question_id.in_([q.id for q in questions]))
        .order_by(Answer.position)
    ).all()
    # Which answer the user picked for each question. Blank questions just aren't in the dict.
    chosen_by_question = dict(session.exec(
        select(AttemptAnswer.question_id, AttemptAnswer.answer_id)
        .where(AttemptAnswer.attempt_id == attempt_id)
    ).all())

    options_by_question = defaultdict(list)
    for a in answers:
        options_by_question[a.question_id].append(ReviewOption(
            id=a.id,
            text=a.answer,
            is_correct=a.is_correct,
            chosen=chosen_by_question.get(a.question_id) == a.id,
        ))

    review = []
    for q in questions:
        options = options_by_question[q.id]
        review.append(ReviewQuestion(
            id=q.id,
            question=q.question,
            is_correct=any(o.chosen and o.is_correct for o in options),
            options=options,
        ))

    return AttemptReviewOut(
        id=attempt.id, quiz_id=quiz.id, quiz_name=quiz.name,
        score=attempt.score, total=len(questions),
        created_at=attempt.created_at, questions=review,
    )

@app.get("/quizzes/{quiz_id}/attempts", response_model=list[AttemptListOut])
def get_attempts(quiz_id: uuid.UUID, user: CurrentUser, session: SessionDep)->list[AttemptListOut]:
    get_owned_quiz(session,quiz_id,user)

    total_questions = session.exec(
        select(func.count()).select_from(Question).where(Question.quiz_id == quiz_id)
    ).one()
    
    attempts = session.exec(
        select(Attempt).where(Attempt.quiz_id == quiz_id).order_by(Attempt.created_at.desc())     
    ).all()

   
    return [
        AttemptListOut(id=a.id, score=a.score, total=total_questions, created_at=a.created_at)
        for a in attempts
    ]