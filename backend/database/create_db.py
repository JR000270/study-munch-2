from sqlmodel import SQLModel, create_engine
from sqlalchemy import text
from models import User, Topic, Chat, Message, Source, Chunk, Quiz, Question, Answer, Attempt, AttemptAnswer, FlashcardDeck, Flashcard  # importing them registers the tables

engine = create_engine("postgresql+psycopg://postgres:devpassword@localhost:5432/postgres", echo=True)
with engine.begin() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
SQLModel.metadata.create_all(engine)