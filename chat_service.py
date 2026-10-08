import uuid
from sqlmodel import Session, select
from llama_index.core.llms import ChatMessage
from db import engine
from database.models import Chat, Message
from agent import build_agent

HISTORY_LIMIT = 20

#pull the previous messages from the database to use as context for the agent
def load_history(session: Session, chat_id: uuid.UUID) -> list[ChatMessage]:
    # Newest N messages, then flipped back into chronological order
    stmt = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_LIMIT)
    )
    rows = list(session.exec(stmt).all())
    rows.reverse()
    return [ChatMessage(role=m.role, content=m.content) for m in rows]


#what is called to chat with the agent and get its response
async def chat_turn(chat_id: uuid.UUID, user_text: str) -> str:
    # --- Transaction 1: look up the chat, load history, save the question ---
    with Session(engine) as session:
        chat = session.get(Chat, chat_id) #pull from the current chats table
        if chat is None:
            raise ValueError("Chat not found")
        topic_id = chat.topic_id                  # derived from the DB, never from the client
        history = load_history(session, chat_id)  # load before saving the new message
        session.add(Message(chat_id=chat_id, role="user", content=user_text)) #add the users message
        session.commit()

    # --- No database session open while the LLM works ---
    agent = build_agent(topic_id)
    handler = agent.run(user_msg=user_text, chat_history=history)
    answer = str(await handler)

    # --- Transaction 2: save the answer ---
    with Session(engine) as session:
        session.add(Message(chat_id=chat_id, role="assistant", content=answer)) #add the agents response to the database
        session.commit()

    return answer