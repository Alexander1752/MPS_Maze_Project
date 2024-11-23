import requests
import time

URL = 'http://127.0.0.1:5000/api/register_agent'
data = {}
response = requests.post(URL, json=data)

print(response.json())