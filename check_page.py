import requests
r = requests.get('http://[::1]:5173/dashboard/bulk-search', timeout=10)
print('BulkSearch page status:', r.status_code)
print('Has root div:', 'id="root"' in r.text)
print('Has script tags:', '<script' in r.text)
print('Length:', len(r.text))