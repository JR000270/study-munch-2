import os
from dotenv import load_dotenv
from sqlmodel import Session, create_engine


load_dotenv("keys.env")
engine = create_engine(os.getenv("DATABASE_URL"))

# FastAPI dependency: one DB session per request.
# Lives here (not in main.py) so auth.py and main.py can both use it
# without importing each other.
def get_session():
    with Session(engine) as session:
        yield session   # FastAPI closes the session after the response is sent