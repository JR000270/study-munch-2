import tiktoken
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select
from llama_index.core.callbacks import CallbackManager, TokenCountingHandler

from database.models import TokenUsage, User

from typing import Annotated
from fastapi import Depends
from sqlmodel import Session
from auth import CurrentUser
from db import engine

def require_budget(user: CurrentUser) -> User:
    with Session(engine) as session:
        ensure_budget(session, user)
    return user

BudgetedUser = Annotated[User, Depends(require_budget)]

def make_token_counter() -> tuple[TokenCountingHandler, CallbackManager]:
    """A fresh counter per request, so users' counts never mix."""
    counter = TokenCountingHandler(tokenizer=tiktoken.get_encoding("o200k_base").encode)
    return counter, CallbackManager([counter])


def month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def tokens_used_this_month(session: Session, user_id) -> int:
    total = session.exec(
        select(func.coalesce(func.sum(TokenUsage.prompt_tokens + TokenUsage.completion_tokens), 0))
        .where(TokenUsage.user_id == user_id, TokenUsage.created_at >= month_start())
    ).one()
    return int(total)


def ensure_budget(session: Session, user: User) -> None:
    if tokens_used_this_month(session, user.id) >= user.token_limit:
        raise HTTPException(status_code=429, detail="Monthly token limit reached")

def record_usage(user_id, feature: str, counter: TokenCountingHandler) -> None:
    with Session(engine) as session:
        session.add(TokenUsage(
            user_id=user_id, feature=feature, model="gpt-4.1",
            prompt_tokens=counter.prompt_llm_token_count,
            completion_tokens=counter.completion_llm_token_count,
        ))
        session.commit()