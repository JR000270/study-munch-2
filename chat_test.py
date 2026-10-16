import sys
import uuid
from chat_service import chat_turn
import asyncio

#to run: python chat_test.py chat_id user_id question

async def main():
    chat_id = uuid.UUID(sys.argv[1])   # past value created from create_chat.py in the run command.
    user_id = uuid.UUID(sys.argv[2])
    question = sys.argv[3] 
    response = await chat_turn(chat_id, user_id, question)
    print(response)

asyncio.run(main())