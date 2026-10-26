
import sys
from sqlmodel import Session, select
from db import engine
from quizzes import generate_quiz, plan_question_count
from passages import sample_note_passages, cap_passages
from database.models import User, Topic, Source

username, topic_name = sys.argv[1], sys.argv[2] #takes username and topic name in command line as arguments 

# --- DB work in a short session ---
with Session(engine) as session:
    #try and reach the users topic if both are valid
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise SystemExit(f"No user named {username}")
    topic = session.exec(
        select(Topic).where(Topic.user_id == user.id, Topic.name == topic_name)
    ).first()
    if topic is None:
        raise SystemExit(f"{username} has no topic named {topic_name!r}")
    #get the topics sources
    sources = session.exec(select(Source).where(Source.topic_id == topic.id)).all()
    print(f"Sources: {[s.name for s in sources]}")
    passages = sample_note_passages(session, [s.id for s in sources])

passages = cap_passages(passages)
num_questions = plan_question_count(len(passages))
print(f"{len(passages)} passages -> asking for {num_questions} questions\n")
for i, p in enumerate(passages, start=1):
    print(f"  [{i}] {p.label}: {p.text[:70]!r}...")

questions = generate_quiz(passages, num_questions)
print(f"\nGot {len(questions)} questions:\n")
for i, question in enumerate(questions, start=1):
    print(f"{i}. Question: {question.question}\n   Correct Choice: {question.options[question.correct_index]}\n  All Answers: ({question.options}) \nSource: ({question.source_label})\n")