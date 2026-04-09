import requests

base = 'http://127.0.0.1:8000'
payload = {'id': 1111, 'password': '1'}
r = requests.post(base + '/user_login', json=payload)
print(r.status_code, r.text)
