import uuid
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Index
from pgvector.sqlalchemy import Vector

def utcnow():
    return datetime.now(timezone.utc)

class User(SQLModel, table=True):
    __tablename__ = "users"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True) #the unique identifier, for the user
    username: str = Field(unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=utcnow)
    token_limit: int = Field(default=50_000, sa_column_kwargs={"server_default": "50000"})

class TokenUsage(SQLModel, table=True):
    __tablename__ = "token_usage"
    __table_args__ = (Index("ix_token_usage_user_created", "user_id", "created_at"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    feature: str  # "chat", "flashcards", "quiz"
    model: str   # "gpt-4.1"
    prompt_tokens: int
    completion_tokens: int
    created_at: datetime = Field(default_factory=utcnow)

class Topic(SQLModel, table=True):
    __tablename__ = "topics"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    name: str
    created_at: datetime = Field(default_factory=utcnow)

#--Topic Resources Section--
class Source(SQLModel, table=True):
    __tablename__ = "sources"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    topic_id: uuid.UUID = Field(foreign_key="topics.id", ondelete="CASCADE")
    name: str
    source_type: str
    storage_path: str
    created_at: datetime = Field(default_factory=utcnow)

class Chunk(SQLModel, table=True):
    __tablename__ = "chunks"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID = Field(foreign_key="sources.id", ondelete="CASCADE")
    chunk_index: int
    content: str
    embedding: list[float] | None = Field(default=None, sa_column=Column(Vector(1536)))
    created_at: datetime = Field(default_factory=utcnow)


#--Chat Section--
class Chat(SQLModel, table=True):
    __tablename__ = "chats"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    topic_id: uuid.UUID = Field(foreign_key="topics.id", ondelete="CASCADE")
    name: str
    created_at: datetime = Field(default_factory=utcnow)

class Message(SQLModel, table=True):
    __tablename__ = "messages"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    chat_id: uuid.UUID = Field(foreign_key="chats.id", ondelete="CASCADE")
    role: str
    content: str
    created_at: datetime = Field(default_factory=utcnow)


# --Quiz Section--
class Quiz(SQLModel, table=True):
    __tablename__ = "quizzes"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    topic_id: uuid.UUID = Field(foreign_key="topics.id", ondelete="CASCADE")
    name: str
    created_at: datetime = Field(default_factory=utcnow)

class Question(SQLModel, table=True):
    __tablename__ ="questions"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    quiz_id: uuid.UUID = Field(foreign_key="quizzes.id", ondelete="CASCADE")
    question: str
    position: int

class Answer(SQLModel, table=True):
    __tablename__ = "answers"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    question_id: uuid.UUID = Field(foreign_key="questions.id", ondelete="CASCADE")
    answer: str
    is_correct: bool
    position: int

class Attempt(SQLModel, table=True):
    __tablename__ = "attempts"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    quiz_id: uuid.UUID = Field(foreign_key="quizzes.id", ondelete="CASCADE")
    score: int
    created_at: datetime = Field(default_factory=utcnow)

class AttemptAnswer(SQLModel, table=True):
    __tablename__ = "attempt_answers"
    attempt_id: uuid.UUID = Field(foreign_key="attempts.id", ondelete="CASCADE", primary_key=True)
    question_id: uuid.UUID = Field(foreign_key="questions.id", ondelete="CASCADE", primary_key=True)
    answer_id: uuid.UUID = Field(foreign_key="answers.id", ondelete="CASCADE")


#--Flashcard Decks Section--
class FlashcardDeck(SQLModel, table=True):
    __tablename__ = "flashcard_decks"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    topic_id: uuid.UUID = Field(foreign_key="topics.id", ondelete="CASCADE")
    name: str
    created_at: datetime = Field(default_factory=utcnow)

class Flashcard(SQLModel, table=True):
    __tablename__ = "flashcards"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    deck_id: uuid.UUID = Field(foreign_key="flashcard_decks.id", ondelete="CASCADE")
    title: str
    content: str