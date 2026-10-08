import asyncio
from dotenv import load_dotenv
from llama_index.core.agent.workflow import FunctionAgent, ToolCall, ToolCallResult
from llama_index.llms.openai import OpenAI
from llama_index.core.workflow import Context
from search_tool import make_search_tool
from wiki_search_tool import make_wiki_search_tool

load_dotenv("keys.env")

SYSTEM_PROMPT = """YYou are a study assistant that answers questions using the user's own notes.

How to research:
1. Always call search_notes first.
2. If the notes don't fully answer every part of the question, call search_wikipedia
   with a short keyword phrase BEFORE answering. Do not ask the user for permission to search.
3. For follow-up questions, rewrite the question as a standalone query (replace words
   like "it" or "that" with what they refer to) and search again. Do not rely only on
   earlier answers.
4. Ignore any retrieved passages that aren't relevant to the question.

How to answer:
- Use only information from the retrieved passages, not your own knowledge.
- Only attribute a claim to a passage if that passage states it directly. Check what
  the subject of each sentence is before using it.
- Do not combine facts from different sentences into a new claim.
- Make the source clear: "Your notes say..." for notes, "Wikipedia adds..." for Wikipedia.
- Cite note passages as [1], [2] and Wikipedia passages as [W1], [W2].
- If neither source answers the question, say so plainly."""


def build_agent(topic_id) -> FunctionAgent:
    return FunctionAgent(
        tools=[make_search_tool(topic_id), make_wiki_search_tool()],
        llm=OpenAI(model="gpt-4.1"),  # pick a current tool-calling model from OpenAI's model list
        system_prompt=SYSTEM_PROMPT,
    )


async def ask(agent: FunctionAgent, question: str, ctx: Context) -> str:

    handler = agent.run(user_msg=question, ctx=ctx)
    # Watch the agent's decisions as they happen
    # traces all the tool calls and the arguments passed to them
    async for event in handler.stream_events():
        if isinstance(event, ToolCall):
            print(f"  -> calling {event.tool_name}({event.tool_kwargs})")
        elif isinstance(event, ToolCallResult):
            preview = event.tool_output.content[:80].replace("\n", " ")
            print(f"  <- got: {preview}...")

    response = await handler
    return str(response)

from sqlmodel import Session, select
from db import engine
from database.models import Topic

# async def main():
#     with Session(engine) as session:
#         topic = session.exec(select(Topic).where(Topic.name == "first test run")).first()

#     agent = build_agent(topic.id)
#     ctx = Context(agent)

#     for q in [
#         "Why is Halloween celebrated on October 31st?",           # notes should be enough
#         "What flavor were the first Doritos?",                    # notes miss -> Wikipedia
#         "What is Samhain and what did people do during it?",      # notes mention it briefly -> maybe both
#         "Where did people celebrate it?",
#     ]:
#         print(f"\nQ: {q}")
#         print(f"A: {await ask(agent, q, ctx)}")

# asyncio.run(main())