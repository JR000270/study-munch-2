from sqlmodel import Session, select
from db import engine
from database.models import Topic, Chat

with Session(engine) as session:
    topic = session.exec(select(Topic).where(Topic.name == "first test run")).first()
    if topic is None:
        raise SystemExit("No test topic found - run test_ingest.py first")

    chat = Chat(topic_id=topic.id, name="memory test")
    session.add(chat)
    session.commit()
    print(f"Created chat: {chat.id}")