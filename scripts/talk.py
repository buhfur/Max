#!/usr/bin/env python3 

import requests 
import json

# Crafted post request to  model 
try:

    res = requests.post(
            "http://localhost:11434/api/chat",
            json={ # json object with prompt and user and specified model 
                "model": "qwen3:8b",
                "messages": [
                    {
                        "role": "user",
                        "content": "Tell me what you know about life", # The actual prompt itself 
                    }
                ],
                "stream": False,
            },
            timeout=60, # Timeout in case of disconnect to free resources  

    )

    res.raise_for_status() # What does this do ? 
    data = res.json()
    print("Sucess:",data["message"]["content"])

except requests.exceptions.HTTPError as http_err:
    print(f"HTTP error occurred: {http_err}") 
except requests.exceptions.JSONDecodeError:
    print("Response could not be decoded as json. Raw text:",response.text)




