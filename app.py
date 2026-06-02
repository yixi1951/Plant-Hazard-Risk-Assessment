import base64
import io
import requests
import socket
import ipaddress
import logging
import re
import sys
from urllib.parse import urlparse
import os
import glob

from flask import Flask, render_template_string, render_template, request, jsonify
app = Flask(__name__)

# ── 临时文件自动清理 ──────────────────────────────────────────
_TMP_DIR = os.path.join(os.getcwd(), 'tmp_uploads')
_MAX_TMP_AGE_SECONDS = 3600  # 1 小时


def _cleanup_tmp_uploads():
    """启动时清理过期临时文件，避免 tmp_uploads/ 无限膨胀。"""
    if not os.path.isdir(_TMP_DIR):
        return
    now = __import__('time').time()
    removed = 0
    for fname in os.listdir(_TMP_DIR):
        fpath = os.path.join(_TMP_DIR, fname)
        if os.path.isfile(fpath):
            age = now - os.path.getmtime(fpath)
            if age > _MAX_TMP_AGE_SECONDS:
                try:
                    os.remove(fpath)
                    removed += 1
                except Exception:
                    pass
    if removed:
        print(f"[cleanup] 已清理 {removed} 个过期临时文件 ({_TMP_DIR})")


_cleanup_tmp_uploads()

from werkzeug.exceptions import RequestEntityTooLarge


@app.errorhandler(RequestEntityTooLarge)
def handle_request_entity_too_large(e):
  max_mb = app.config.get('MAX_CONTENT_LENGTH', 0) // (1024 * 1024)
  logger.warning(
    'RequestEntityTooLarge on %s from %s content_length=%s max_mb=%s',
    request.path,
    request.remote_addr,
    request.content_length,
    max_mb,
  )
  err_msg = f"上传或评估失败：上传文件太大（最大支持 {max_mb} MB）。请压缩图片或使用图片 URL 上传。"
  return render_template("index.html", error=err_msg), 413


@app.before_request
def log_request_before_request():
  logger.info(
    'Before request %s %s content_length=%s content_type=%s',
    request.method,
    request.path,
    request.content_length,
    request.content_type,
  )


@app.after_request
def add_no_cache_headers(response):
  if response.mimetype == 'text/html':
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
  return response


@app.errorhandler(Exception)
def handle_unexpected_exception(e):
  if isinstance(e, RequestEntityTooLarge):
    return handle_request_entity_too_large(e)
  logger.exception('Unhandled exception on %s from %s: %s', request.path, request.remote_addr, e)
  return render_template("index.html", error=f"服务器内部错误：{e}"), 500

@app.route('/favicon.ico')
def favicon():
  return send_from_directory('static', 'favicon.svg', mimetype='image/svg+xml')

@app.route("/about")
def about():
  return render_template("about.html")

@app.route("/team")
def team():
  return render_template("team.html")

@app.route("/faq")
def faq():
  return render_template("faq.html")

@app.route("/api")
def api_doc():
  return render_template("api.html")

from PIL import Image

from scripts.inference_utils import predict_image, predict_with_uncertainty, load_model
import json
from datetime import datetime

# ── 启动模型校验 ──────────────────────────────────────────
_MODEL_PATH = os.environ.get('MODEL_PATH', 'best_multitask_model.pth')
if os.path.exists(_MODEL_PATH):
    try:
        _model, _device, _meta = load_model(model_path=_MODEL_PATH)
        logging.getLogger(__name__).info(
            '✅ 模型加载成功: %s (device=%s num_diseases=%s)',
            _MODEL_PATH, _device,
            _meta.get('num_diseases', '?'),
        )
    except Exception as exc:
        logging.getLogger(__name__).warning(
            '⚠️ 模型加载失败: %s (%s: %s). 运行时预测将按需重试。',
            _MODEL_PATH, type(exc).__name__, exc,
        )
else:
    logging.getLogger(__name__).warning(
        '⚠️ 模型文件不存在: %s. 请将模型权重放置于项目根目录，或设置环境变量 MODEL_PATH。',
        _MODEL_PATH,
    )
from flask import send_from_directory, url_for
from PIL import ImageDraw, ImageFont


# Max upload size (in bytes). Default 10 MB, can be overridden with env var MAX_UPLOAD_MB
try:
  _max_mb = int(os.environ.get('MAX_UPLOAD_MB', '10'))
except Exception:
  _max_mb = 10
app.config['MAX_CONTENT_LENGTH'] = _max_mb * 1024 * 1024

# logging
logging.basicConfig(
  level=logging.INFO,
  format='[%(asctime)s] %(levelname)s: %(message)s',
  stream=sys.stdout,
  force=True,
)
logger = logging.getLogger('agri_app')
logger.setLevel(logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.INFO)

_file_handler = logging.FileHandler(os.path.join(os.getcwd(), 'server_debug.log'), encoding='utf-8')
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s'))
logger.addHandler(_file_handler)
logging.getLogger().addHandler(_file_handler)


class RequestLogMiddleware:
  def __init__(self, app):
    self.app = app

  def __call__(self, environ, start_response):
    method = environ.get('REQUEST_METHOD', '-')
    path = environ.get('PATH_INFO', '-')
    content_length = environ.get('CONTENT_LENGTH', '-')
    remote_addr = environ.get('REMOTE_ADDR', '-')
    logger.info('Incoming request %s %s from %s content_length=%s', method, path, remote_addr, content_length)
    try:
      max_length = int(app.config.get('MAX_CONTENT_LENGTH') or 0)
      body_length = int(content_length) if content_length not in ('', '-', None) else 0
      if max_length and body_length > max_length:
        logger.warning(
          'Rejected request in middleware %s %s from %s content_length=%s max_length=%s',
          method,
          path,
          remote_addr,
          body_length,
          max_length,
        )
        response_body = b'413 Request Entity Too Large\n'
        headers = [
          ('Content-Type', 'text/plain; charset=utf-8'),
          ('Content-Length', str(len(response_body))),
        ]
        start_response('413 REQUEST ENTITY TOO LARGE', headers)
        return [response_body]
    except Exception as exc:
      logger.exception('Middleware size check failed for %s %s: %s', method, path, exc)
    return self.app(environ, start_response)


app.wsgi_app = RequestLogMiddleware(app.wsgi_app)

# simple filename sanitization
_FILENAME_BAD_RE = re.compile(r"\.(php|phtml|exe|sh|js|py)$", re.IGNORECASE)
_ALLOWED_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff'}
_ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG', 'BMP', 'GIF', 'TIFF', 'WEBP'}


def _detect_image_signature(data: bytes):
  if not data:
    return None
  if data.startswith(b'\xff\xd8\xff'):
    return 'JPEG'
  if data.startswith(b'\x89PNG\r\n\x1a\n'):
    return 'PNG'
  if data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
    return 'GIF'
  if data.startswith(b'BM'):
    return 'BMP'
  if data.startswith(b'\x00\x00\x01\x00'):
    return 'ICO'
  if len(data) >= 12 and data[0:4] == b'RIFF' and data[8:12] == b'WEBP':
    return 'WEBP'
  if data.startswith(b'II*\x00') or data.startswith(b'MM\x00*'):
    return 'TIFF'
  return None


def _open_validated_image(data: bytes, source_label: str):
  signature = _detect_image_signature(data)
  if signature is None:
    logger.warning('Blocked %s with unknown image signature', source_label)
    raise ValueError('上传内容不是受支持的图片格式')

  if signature not in _ALLOWED_IMAGE_FORMATS:
    logger.warning('Blocked %s with unsupported image signature: %s', source_label, signature)
    raise ValueError(f'上传图片格式不支持：{signature}')

  try:
    image = Image.open(io.BytesIO(data))
    image.load()
  except Exception as exc:
    logger.warning('Failed to decode %s as image: %s', source_label, exc)
    raise ValueError('图片文件损坏或格式不正确') from exc

  detected_format = (image.format or '').upper()
  if detected_format == 'JPG':
    detected_format = 'JPEG'
  if detected_format not in _ALLOWED_IMAGE_FORMATS:
    logger.warning('Blocked %s with decoded format %s', source_label, detected_format)
    raise ValueError(f'图片格式不支持：{detected_format or "UNKNOWN"}')

  if detected_format != signature and not (signature == 'JPEG' and detected_format == 'JPEG'):
    logger.warning('Rejected %s due to format mismatch: signature=%s decoded=%s', source_label, signature, detected_format)
    raise ValueError('图片内容与文件签名不一致')

  return image.convert('RGB'), detected_format

def _host_resolves_to_private(hostname: str) -> bool:
  try:
    infos = socket.getaddrinfo(hostname, None)
    for info in infos:
      addr = info[4][0]
      try:
        ip = ipaddress.ip_address(addr)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
          return True
      except Exception:
        continue
  except Exception:
    # if DNS fails, err on the side of safety by denying
    return True
  return False


@app.route("/", methods=["GET", "POST"])
def index():
  result = None
  error = None
  preview_b64 = None
  preview_token = None
  debug_path = None

  def _bytes_from_source(file, image_url):
    # returns bytes or raises
    if (not file or not file.filename) and image_url:
      parsed = urlparse(image_url)
      if parsed.scheme not in ("http", "https"):
        raise ValueError("仅支持 http/https 图片 URL")
      host = parsed.hostname or ""
      # reject obvious local/loopback hostnames and private-resolving hosts
      if host.lower().startswith('localhost') or host.startswith('127.'):
        logger.warning('Blocked request to localhost or loopback host: %s', host)
        raise ValueError("拒绝下载内网或本地地址")
      if _host_resolves_to_private(host):
        logger.warning('Blocked request: host resolves to private IPs: %s', host)
        raise ValueError("拒绝下载内网或本地地址")

      try:
        resp = requests.get(image_url, timeout=6, stream=True)
        resp.raise_for_status()
      except Exception as re:
        logger.warning('Failed to download URL %s : %s', image_url, re)
        raise ValueError(f"无法下载图片: {re}")

      ct = (resp.headers.get('Content-Type') or '').lower()
      if not ct.startswith('image/'):
        logger.warning('Blocked non-image URL content-type: %s for %s', ct, image_url)
        raise ValueError('下载的资源不是图片 (Content-Type 非 image/*)')

      cl = resp.headers.get("Content-Length")
      max_bytes = app.config.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024)
      if cl:
        try:
          if int(cl) > max_bytes:
            raise ValueError("图片太大，最大支持 5MB")
        except Exception:
          pass
      data = resp.content
      if len(data) > max_bytes:
        raise ValueError("图片太大，最大支持 5MB")

      if _detect_image_signature(data) is None:
        logger.warning('Blocked URL with unknown image signature: %s', image_url)
        raise ValueError('下载内容不是受支持的图片格式')
      return data
    else:
      # uploaded file: perform basic checks
      filename = getattr(file, 'filename', '') or ''
      if _FILENAME_BAD_RE.search(filename):
        logger.warning('Blocked upload with suspicious filename: %s', filename)
        raise ValueError('上传文件名含可疑扩展名，已被拒绝')

      # read content and enforce size limit
      data = file.read()
      max_bytes = app.config.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024)
      if data and len(data) > max_bytes:
        logger.warning('Blocked upload too large: %s bytes (file=%s)', len(data), filename)
        raise ValueError('上传文件过大，最大支持 5MB')

      # simple extension check
      _, ext = os.path.splitext(filename.lower())
      if ext and ext not in _ALLOWED_EXTS:
        logger.warning('Upload filename extension not allowed: %s', ext)
        # still allow if content is valid image, we'll verify later via PIL

      if _detect_image_signature(data) is None:
        logger.warning('Blocked upload with unknown image signature: %s', filename)
        raise ValueError('上传内容不是受支持的图片格式')
      return data

  def _decode_bytes_to_image(data):
    nonlocal debug_path
    if not data:
      raise ValueError("上传文件为空")
    prefix = (data[:40] or b"").lower()
    if prefix.startswith(b"[internetshortcut]") or b"url=" in prefix or prefix.startswith(b"http"):
      raise ValueError("检测到上传内容像是链接/快捷方式 (.url)，不是图片。请在浏览器中右键图片->另存为，然后再上传本地图片。")

    return _open_validated_image(data, 'upload')[0]

  def _normalize_preview_b64(value):
    if not value:
      return ""
    if value.startswith("data:") and "," in value:
      return value.split(",", 1)[1]
    return value

  def _image_from_preview_b64(value):
    normalized = _normalize_preview_b64(value)
    if not normalized:
      raise ValueError("请先生成预览，再开始评估。")
    decoded = base64.b64decode(normalized)
    return _decode_bytes_to_image(decoded)

  if request.method == "POST":
    action = (request.form.get("action") or "predict").lower()
    file = request.files.get("image")
    image_url = (request.form.get("image_url") or "").strip()
    # preview_b64 may be carried from previous preview
    carried_preview = request.form.get("preview_b64")

    if (not file or not file.filename) and not image_url and not carried_preview:
      error = "请先选择一张图片或输入图片 URL，然后预览或直接评估。"
    else:
      try:
        if action == "preview":
          # produce preview_b64 and return
          if carried_preview:
            preview_b64 = _normalize_preview_b64(carried_preview)
          else:
            data = _bytes_from_source(file, image_url)
            logger.info("Preview upload bytes=%s", len(data) if data is not None else 'None')
            image = _decode_bytes_to_image(data)
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            preview_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            # save raw upload to tmp directory and return a token so predict step does not need to re-upload
            tmp_dir = os.path.join(os.getcwd(), 'tmp_uploads')
            os.makedirs(tmp_dir, exist_ok=True)
            try:
              import uuid
              token = f'{uuid.uuid4().hex}.bin'
              tmp_path = os.path.join(tmp_dir, token)
              with open(tmp_path, 'wb') as fh:
                fh.write(data)
              preview_token = token
            except Exception:
              preview_token = None
        else:
          # predict
          # support preview carried as token (server-side temp file) or base64
          token_from_form = (request.form.get('preview_token') or '').strip()
          if token_from_form:
            tmp_path = os.path.join(os.getcwd(), 'tmp_uploads', token_from_form)
            if not os.path.exists(tmp_path):
              raise ValueError('预览已过期或不存在，请重新预览。')
            with open(tmp_path, 'rb') as fh:
              data = fh.read()
            # 用完即删临时文件
            try:
              os.remove(tmp_path)
            except Exception:
              pass
            image = _decode_bytes_to_image(data)
            # also populate preview_b64 for template rendering
            buf = io.BytesIO()
            image.save(buf, format='PNG')
            preview_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            preview_token = token_from_form
          elif file and getattr(file, 'filename', ''):
            # Fallback: allow direct prediction from the uploaded file when preview_b64 is missing.
            data = _bytes_from_source(file, image_url)
            image = _decode_bytes_to_image(data)
            buf = io.BytesIO()
            image.save(buf, format='PNG')
            preview_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
          else:
            if not carried_preview:
              raise ValueError("请先预览成功，再开始评估。")
            preview_b64 = _normalize_preview_b64(carried_preview)
            image = _image_from_preview_b64(carried_preview)

          # optional MC dropout samples (传表单 mc_samples)
          try:
            mc_samples = int(request.form.get('mc_samples') or 0)
          except Exception:
            mc_samples = 0

          if mc_samples and mc_samples > 1:
            annotated, summary, probabilities, meta = predict_with_uncertainty(image, mc_samples=mc_samples)
          else:
            annotated, summary, probabilities, meta = predict_image(image)

          buffer = io.BytesIO()
          annotated.save(buffer, format="PNG")
          annotated_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

          # generate report files (JSON + simple PDF) and expose paths
          reports_dir = os.path.join(os.getcwd(), 'reports')
          os.makedirs(reports_dir, exist_ok=True)
          now = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
          base_name = f'report_{now}'
          json_path = f'{base_name}.json'
          pdf_path = f'{base_name}.pdf'

          report_obj = {
            'summary': summary,
            'probabilities': probabilities,
            'meta': meta,
            'generated_at': now,
          }
          with open(os.path.join(reports_dir, json_path), 'w', encoding='utf-8') as fh:
            json.dump(report_obj, fh, ensure_ascii=False, indent=2)

          # simple PDF: paste annotated image on top, text below
          try:
            img_buf = io.BytesIO(base64.b64decode(annotated_b64))
            ann = Image.open(img_buf).convert('RGB')
            w, h = ann.size
            text_area_h = 220
            canvas = Image.new('RGB', (w, h + text_area_h), (255, 255, 255))
            canvas.paste(ann, (0, 0))
            draw = ImageDraw.Draw(canvas)
            try:
              font = ImageFont.truetype('arial.ttf', 16)
            except Exception:
              font = ImageFont.load_default()
            text_y = h + 12
            lines = (summary + '\n\n' + json.dumps(meta, ensure_ascii=False)).split('\n')
            for line in lines:
              draw.text((12, text_y), line, fill=(0, 0, 0), font=font)
              text_y += 18
            canvas.save(os.path.join(reports_dir, pdf_path), format='PDF')
          except Exception:
            # fallback: save annotated PNG only and skip PDF
            pdf_path = None

          result = {
            "annotated_image": annotated_b64,
            "summary": summary,
            "probabilities": probabilities,
            "meta": meta,
            "report_json": (url_for('download_report', fname=json_path) if os.path.exists(os.path.join(reports_dir, json_path)) else None),
            "report_pdf": (url_for('download_report', fname=pdf_path) if pdf_path and os.path.exists(os.path.join(reports_dir, pdf_path)) else None),
          }
          logger.info('Generated report %s (pdf=%s) for request from %s', json_path, pdf_path, request.remote_addr)
      except Exception as exc:
        logger.exception('Failed to process request')
        if debug_path:
          error = f"图片处理失败：{exc} (已保存原始上传为: {debug_path})"
        else:
          error = f"图片处理失败：{exc}"

  # prepare chart data for ECharts frontend using recent reports (falls back to demo)
  chart_data = None
  try:
    reports_dir = os.path.join(os.getcwd(), 'reports')
    labels = []
    risk = []
    suggestion = []
    confidence_series = []

    if os.path.isdir(reports_dir):
      files = sorted(glob.glob(os.path.join(reports_dir, '*.json')), key=os.path.getmtime)
      if files:
        last = files[-7:]
        for f in last:
          try:
            with open(f, 'r', encoding='utf-8') as fh:
              obj = json.load(fh)
            gen = obj.get('generated_at') or os.path.basename(f)
            labels.append(gen)
            meta = obj.get('meta', {}) or {}
            dr = meta.get('disease_risk_percent')
            if dr is None:
              dr = meta.get('disease_risk') or meta.get('risk_percent') or 50
            try:
              drv = int(dr)
            except Exception:
              drv = int(float(dr) if dr else 50)
            risk.append(max(0, min(100, drv)))
            # suggestion: simple heuristic derived from risk
            suggestion.append(max(0, min(100, 60 + (50 - drv) // 1)))
            sc = meta.get('severity_confidence') or meta.get('confidence') or 0.95
            try:
              csv = float(sc) * 100
            except Exception:
              csv = 95.0
            confidence_series.append(max(0, min(100, int(csv))))
          except Exception:
            continue

    if labels:
      chart_data = {'labels': labels, 'risk': risk, 'suggestion': suggestion, 'confidence': confidence_series}
    else:
      if result:
        meta = result.get('meta', {}) if isinstance(result, dict) else {}
        base = int(meta.get('disease_risk_percent', 50)) if meta else 50
        confidence = float(meta.get('severity_confidence', 0.95)) * 100 if meta else 95.0
        labels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        risk = [max(0, min(100, base + d)) for d in (-6, -3, 0, 4, 1, -2, -5)]
        suggestion = [max(0, min(100, 60 + i * 3)) for i in range(7)]
        confidence_series = [max(0, min(100, int(confidence + d))) for d in (-5, -2, 0, 1, 2, -1, -4)]
        chart_data = {'labels': labels, 'risk': risk, 'suggestion': suggestion, 'confidence': confidence_series}
  except Exception:
    chart_data = None

  chart_json = json.dumps(chart_data, ensure_ascii=False) if chart_data is not None else 'null'
  return render_template("index.html", result=result, error=error, preview_b64=preview_b64, preview_token=preview_token, chart_data=chart_json)



@app.route('/batch_predict', methods=['POST'])
def batch_predict():
    """批量预测接口：接受多张图片或ZIP压缩包，返回JSON结果数组。"""
    import zipfile
    import tempfile

    images_to_process = []
    error_prefix = ""

    # 1) 收集图片 ── 从 batch_images 字段 (multiple files)
    batch_files = request.files.getlist('batch_images')
    for f in batch_files:
        if f and f.filename:
            data = f.read()
            if len(data) > app.config.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024):
                continue  # skip oversized
            if _detect_image_signature(data) is not None:
                images_to_process.append((f.filename, data))

    # 2) 收集图片 ── 从 batch_zip 字段 (ZIP 压缩包)
    zip_file = request.files.get('batch_zip')
    if zip_file and zip_file.filename and zip_file.filename.lower().endswith('.zip'):
        try:
            zip_data = zip_file.read()
            with tempfile.TemporaryDirectory() as tmpdir:
                zippath = os.path.join(tmpdir, 'batch.zip')
                with open(zippath, 'wb') as fh:
                    fh.write(zip_data)
                with zipfile.ZipFile(zippath, 'r') as zf:
                    for info in zf.infolist():
                        if info.filename.startswith('__') or info.filename.startswith('.'):
                            continue
                        ext = os.path.splitext(info.filename.lower())[1]
                        if ext not in _ALLOWED_EXTS:
                            continue
                        try:
                            img_data = zf.read(info)
                            if _detect_image_signature(img_data) is not None:
                                images_to_process.append((info.filename, img_data))
                        except Exception:
                            continue
        except Exception as exc:
            logger.warning('Failed to process batch zip: %s', exc)
            return jsonify({'error': f'ZIP 解压失败: {exc}'}), 400

    if not images_to_process:
        return jsonify({'error': '未找到有效的图片文件。支持直接上传图片或 ZIP 压缩包。'}), 400

    results = []
    for fname, img_data in images_to_process:
        try:
            image = _decode_bytes_to_image(img_data)
            annotated, summary, probabilities, meta = predict_image(image)
            results.append({
                'filename': fname,
                'disease_name': meta.get('disease_name', '未知'),
                'severity': meta.get('severity', '未知'),
                'risk_score': meta.get('disease_risk_percent'),
                'confidence': round(meta.get('disease_confidence', 0) * 100, 2),
                'severity_confidence': round(meta.get('severity_confidence', 0) * 100, 2),
                'summary': summary,
            })
        except Exception as exc:
            logger.warning('Batch predict failed for %s: %s', fname, exc)
            results.append({
                'filename': fname,
                'error': str(exc),
            })

    return jsonify({'results': results, 'total': len(results)})


@app.route('/reports/<path:fname>')
def download_report(fname):
  reports_dir = os.path.join(os.getcwd(), 'reports')
  if not os.path.exists(os.path.join(reports_dir, fname)):
    return ('Not found', 404)
  return send_from_directory(reports_dir, fname, as_attachment=True)


if __name__ == "__main__":
  host = os.environ.get("APP_HOST", "0.0.0.0")
  port = int(os.environ.get("APP_PORT", "7860"))
  print(f"Starting Flask app on {host}:{port}")
  app.run(host=host, port=port, debug=False)