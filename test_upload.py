from PIL import Image
import io
import requests

img = Image.new('RGB', (200, 200), (255, 0, 0))
buf = io.BytesIO()
img.save(buf, 'PNG')
buf.seek(0)

resp = requests.post('http://127.0.0.1:7860/', files={'image': ('test.png', buf, 'image/png')})
print('status', resp.status_code)
print(resp.text[:2000])
