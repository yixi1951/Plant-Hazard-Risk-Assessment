import requests

url = 'https://via.placeholder.com/150'
resp = requests.post('http://127.0.0.1:7860/', data={'image_url': url})
print('status', resp.status_code)
print(resp.text[:1000])
