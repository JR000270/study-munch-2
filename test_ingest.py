from sqlmodel import Session
from llama_index.core import SimpleDirectoryReader
from db import engine
from database.models import User, Topic, Source
from chunking import ingest_source

with Session(engine) as session:
    #create a user, topic and source. Python->SQL
    user = User(username="tester1", password_hash="not-a-real-hash")
    topic = Topic(user_id=user.id, name="first test run")
    source = Source(topic_id=topic.id, name="sample.txt",
                    source_type="upload", storage_path="sample.txt")
    #session.add_all([user, topic, source])
    session.add(user)
    session.flush()
    session.add(topic)
    session.flush()
    session.add(source)
    session.commit()

    documents = SimpleDirectoryReader(input_files=["sample.txt"]).load_data()
    count = ingest_source(session=session, source=source, documents=documents)
    print(f"Saved {count} chunks")