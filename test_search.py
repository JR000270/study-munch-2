from sqlmodel import Session, select
from db import engine
from database.models import Topic
from chunking import search_chunks

with Session(engine) as session:
    # find the topic created by test_ingest.py
    topic = session.exec(select(Topic).where(Topic.name == "first test run")).first()
    if topic is None:
        raise SystemExit("No test topic found - run test_ingest.py first")

    question = "Are doritos orange because of Donald Trump?"
    results = search_chunks(session=session, topic_id=topic.id, question=question, k=3)

    print(f"Q: {question}\n")
    for chunk, source, distance in results:
        print(f"[{chunk.chunk_index}] distance={distance:.4f}  {chunk.content[:100]}")
