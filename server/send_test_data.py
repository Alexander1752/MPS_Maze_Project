"""This file will send info to the server in order to check the corectness"""
import requests

URL = 'http://127.0.0.1:5000/api/register_agent'
data = {}
response = requests.post(URL, json=data)


URL = 'http://127.0.0.1:5000/api/receive_moves'
data = {'UUID': '1', 'input': 'NNNSEEESW'}
response = requests.post(URL, json=data)

print(response.json())