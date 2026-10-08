from sqlmodel import Session, select
from tools.db import engine
from database.models import Topic
from tools.chunking import search_chunks
from tools.search_tool import make_search_tool

with Session(engine) as session:
    # find the topic created by test_ingest.py
    topic = session.exec(select(Topic).where(Topic.name == "first test run")).first()
    if topic is None:
        raise SystemExit("No test topic found - run test_ingest.py first")

    #testing method from chunking
    # question = "Are doritos orange because of Donald Trump?"
    # results = search_chunks(session=session, topic_id=topic.id, question=question, k=3)

    # print(f"Q: {question}\n")
    # for chunk, source, distance in results:
    #     print(f"[{chunk.chunk_index}] distance={distance:.4f}  {chunk.content[:100]}")

    #testing search tool
    tool = make_search_tool(topic.id)
    print(tool.metadata.name)
    print(tool.metadata.description)   # this is what the LLM will see
    print("question 1: ", tool.call(query="Why is Halloween on October 31st?").content)
    print("question 2: ", tool.call(query="How is Día de los Muertos celebrated in Mexico?").content)


