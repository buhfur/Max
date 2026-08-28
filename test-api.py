#!/usr/bin/env python3 

import requests 
import json 
import os

key = os.environ["OT_KEY"]
url = "http://localhost:8000/files/read"

params = {
        "path": "/home/buhfur/.zshrc"
}
        


def test_execute():
    res = requests.get(
            url,
            params=params,
            headers={
                "Authorization": f"Bearer {key}",
                "Accept": "application/json"
            },
            timeout=10,
        )

    res.raise_for_status()
    print(res.status_code) 
    return json.dumps(res.json())

if __name__ == "__main__":
    print(test_execute())


