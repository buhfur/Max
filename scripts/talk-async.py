#!/usr/bin/env python3 
from ollama import Client
from ollama import chat
from ollama import ChatResponse
from ollama import AsyncClient
import asyncio 
# same but asynchronous 


async def chat(): 
    message = {'role': 'user', 'content':'Help me understand fastapi in python3?'}
    async for part in await AsyncClient().chat(model='qwen3:8b',messages=[message],stream=True): # Spins up asynchronous client  
        print(part['message']['content'], end='', flush=True)


asyncio.run(chat())



