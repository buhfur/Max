#!/usr/bin/env python3 
from ollama import Client
from ollama import chat
from ollama import ChatResponse
# Using  ollama libraries instead of requests alone 


client = Client(
        host='http://localhost:11434',
        #headers={} # Headers statement could be for  custom headers if a reverse proxy or nginx is used 
        )

response = client.chat(
        model='qwen3:8b', 
        messages=[{'role': 'user', 'content': 'What does the model actually look like under the hood, like the array of keywords' }],
        stream=True
)

for part in response:
    print(part['message']['content'],end='',flush=True)
