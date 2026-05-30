import io
import base64
from PIL import Image
import requests

BASE = 'http://127.0.0.1:7860/'

# Generate a red square PNG
img = Image.new('RGB', (200, 200), (255, 0, 0))
buf = io.BytesIO()
img.save(buf, 'PNG')
buf.seek(0)

# Step 1: preview with file upload
files = {'image': ('test.png', buf, 'image/png')}
data = {'action': 'preview'}
print('Posting preview (file)...')
resp = requests.post(BASE, files=files, data=data)
print('preview status', resp.status_code)
html = resp.text
idx = html.find('data:image/png;base64,')
if idx == -1:
    print('No preview image found in response')
    print(html[:1000])
    raise SystemExit(1)
start = idx + len('data:image/png;base64,')
end = html.find('"', start)
preview_b64 = html[start:end]
print('Got preview length', len(preview_b64))

# Step 2: predict using preview_b64
print('Posting predict with preview_b64...')
resp2 = requests.post(BASE, data={'action': 'predict', 'preview_b64': preview_b64})
print('predict status', resp2.status_code)
html2 = resp2.text
# find annotated image
idx2 = html2.find('data:image/png;base64,')
if idx2 == -1:
    print('No annotated image found in response')
    print(html2[:1000])
    raise SystemExit(1)
start2 = idx2 + len('data:image/png;base64,')
end2 = html2.find('"', start2)
annot_b64 = html2[start2:end2]
print('Got annotated length', len(annot_b64))
# save annotated image
with open('annotated_test.png', 'wb') as f:
    f.write(base64.b64decode(annot_b64))
print('Saved annotated_test.png')
print('Done')
