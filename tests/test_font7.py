import requests
import re

token = 'fiNN9Tq09m0aOGs2DMIc7g88x3KZ85AT2xBbIU_DXQM'
headers = {'Authorization': f'Bearer {token}', 'X-User-Id': '1'}

r = requests.post('http://127.0.0.1:8000/api/bulk-generate-draft-from-template', 
                  json={'lead_ids': [21448], 'template_name': 'palak_mam_Draft_1'}, 
                  headers=headers, timeout=30)
batch_id = r.json()['batch_id']

import time
for i in range(10):
    time.sleep(1)
    r = requests.get(f'http://127.0.0.1:8000/api/bulk-progress/{batch_id}', headers=headers)
    if r.json().get('status') == 'done':
        break

r = requests.get('http://127.0.0.1:8000/api/pending-drafts?status=PENDING_APPROVAL&per_page=1', headers=headers)
drafts = r.json().get('drafts', [])
if drafts:
    draft = drafts[0]
    html_body = draft.get('html_body', '')
    matches = re.findall(r'font-family:[^>]*', html_body)
    for m in matches:
        print(m)