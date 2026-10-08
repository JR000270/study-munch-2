import sys
import uuid
from chat_service import chat_turn
import asyncio

#python chat_test.py chat_id_val question

async def main():
    chat_id = uuid.UUID(sys.argv[1])   # past value created from create_chat.py in the run command.
    question = sys.argv[2] 
    response = await chat_turn(chat_id, question)
    print(response)

asyncio.run(main())