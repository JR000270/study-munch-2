import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlmodel import Session, select

from db import engine
from database.models import User

load_dotenv("keys.env")

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is missing from keys.env")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Argon2 is the current recommended password hash: deliberately slow and
# memory-hungry, so guessing passwords from a stolen DB is expensive.
password_hasher = PasswordHash.recommended()

# Hash of a throwaway password, used when the username doesn't exist (see authenticate_user).
DUMMY_HASH = password_hasher.hash("timing-attack-dummy-password")

# Tells FastAPI: "read a Bearer token from the Authorization header".
# tokenUrl is where clients log in; /docs uses it for its Authorize button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


# ---------- Passwords ----------
def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except Exception:
        # e.g. old test rows with password_hash="not-a-real-hash" aren't valid hashes
        return False


def authenticate_user(session: Session, username: str, password: str) -> User | None:
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        # Still do a full hash check so "unknown user" takes as long as "wrong password".
        # Otherwise an attacker could time responses to discover which usernames exist.
        verify_password(password, DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# ---------- Tokens ----------
def create_access_token(user_id: uuid.UUID) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expires}   # "sub" = subject = who this token is about
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ---------- The dependency every protected endpoint uses ----------
def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # algorithms=[...] is required on purpose: never let the token itself
        # choose how it gets verified.
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])  # also checks "exp"
        user_id = uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise credentials_error

    # Short session of its own, closed right away, so async endpoints like
    # send_message don't hold a DB connection open during the LLM call.
    with Session(engine) as session:
        user = session.get(User, user_id)
    if user is None:   # token is valid but the account was deleted
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]