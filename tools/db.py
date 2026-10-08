import os
from dotenv import load_dotenv
from sqlmodel import create_engine

load_dotenv("keys.env")
engine = create_engine(os.getenv("DATABASE_URL"))