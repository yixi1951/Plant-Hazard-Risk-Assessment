import base64
import io
import requests
import socket
import ipaddress
import logging
import re
from urllib.parse import urlparse
import os

from flask import Flask, render_template_string, render_template, request, jsonify
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

from scripts.inference_utils import predict_image, predict_with_uncertainty
import json
from datetime import datetime
from flask import send_from_directory, url_for
from PIL import ImageDraw, ImageFont


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB limit for uploads

# logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger('agri_app')

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


HTML = r"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>智农 · 农作物病虫害AI智能识别预警系统</title>
  <style>
    :root {
      --bg0: #f3fbf4;
      --bg1: #e5f7e8;
      --bg2: #d2efda;
      --card: rgba(255, 255, 255, 0.82);
      --card2: rgba(249, 253, 250, 0.92);
      --line: rgba(34, 197, 94, 0.14);
      --line-strong: rgba(34, 197, 94, 0.24);
      --text: #16301f;
      --muted: #4b6a57;
      --accent: #16a34a;
      --accent-2: #22c55e;
      --danger: #dc2626;
      --shadow: 0 24px 70px rgba(28, 87, 45, .10);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      color: var(--text);
      font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
      background:
        radial-gradient(circle at 12% 16%, rgba(34, 197, 94, .14), transparent 24%),
        radial-gradient(circle at 84% 10%, rgba(132, 204, 22, .14), transparent 21%),
        radial-gradient(circle at 80% 78%, rgba(34, 197, 94, .10), transparent 26%),
        linear-gradient(180deg, var(--bg0), var(--bg1) 45%, var(--bg2));
      min-height: 100vh;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: .12;
      background-image:
        linear-gradient(rgba(22,48,31,.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(22,48,31,.05) 1px, transparent 1px);
      background-size: 38px 38px;
      mask-image: linear-gradient(180deg, rgba(0,0,0,.8), transparent 90%);
    }
    .wrap { max-width: 1320px; margin: 0 auto; padding: 28px 18px 56px; position: relative; }
    .topbar {
      position: sticky;
      top: 12px;
      z-index: 20;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 14px 18px;
      margin-bottom: 18px;
      border-radius: 20px;
      border: 1px solid rgba(34, 197, 94, .14);
      background: rgba(255, 255, 255, .72);
      backdrop-filter: blur(18px);
      box-shadow: var(--shadow);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }
    .brand-mark {
      width: 44px;
      height: 44px;
      border-radius: 14px;
      display: grid;
      place-items: center;
      background: linear-gradient(135deg, #34d399, #22c55e);
      color: #062011;
      font-weight: 900;
      box-shadow: 0 10px 18px rgba(34, 197, 94, .20);
      flex: 0 0 auto;
    }
    .brand-copy strong { display: block; font-size: 16px; }
    .brand-copy span { display: block; color: var(--muted); font-size: 12px; margin-top: 2px; }
    .nav-links { display: flex; flex-wrap: wrap; gap: 8px; }
    .nav-links a {
      text-decoration: none;
      color: var(--text);
      padding: 9px 12px;
      border-radius: 999px;
      border: 1px solid transparent;
      background: rgba(34, 197, 94, .08);
      font-size: 13px;
    }
    .nav-links a:hover { border-color: rgba(34, 197, 94, .24); background: rgba(34, 197, 94, .12); }
    .hero {
      display: grid;
      grid-template-columns: 1.08fr .92fr;
      gap: 20px;
      margin-bottom: 20px;
      align-items: stretch;
    }
    .panel {
      background: linear-gradient(180deg, rgba(255, 255, 255, .92), rgba(247, 252, 248, .90));
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
    }
    .hero-copy, .hero-side, .section, .results { padding: 26px; }
    .eyebrow {
      display: inline-flex; align-items: center; gap: 8px;
      padding: 8px 14px; border-radius: 999px;
      color: #14532d; background: rgba(34, 197, 94, .10);
      border: 1px solid rgba(34, 197, 94, .22); font-size: 13px; letter-spacing: .2px;
    }
    .hero-copy h1 {
      margin: 16px 0 12px;
      font-size: clamp(34px, 4vw, 58px);
      line-height: 1.04;
      letter-spacing: -0.02em;
    }
    .hero-copy p {
      margin: 0;
      font-size: 16px;
      line-height: 1.85;
      color: var(--muted);
      max-width: 62ch;
    }
    .hero-highlights { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
    .chip {
      padding: 9px 12px; border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(34,197,94,.06);
      color: #1f5130; font-size: 13px;
    }
    .hero-side {
      display: grid; gap: 16px;
      grid-template-rows: auto 1fr;
    }
    .side-card {
      border-radius: 20px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,.86), rgba(244, 251, 246, .92));
      padding: 18px;
    }
    .stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 14px; }
    .stat {
      padding: 14px 12px; border-radius: 16px;
      background: rgba(34,197,94,.06);
      border: 1px solid var(--line);
    }
    .stat strong { display: block; font-size: 20px; margin-bottom: 4px; }
    .stat span { color: var(--muted); font-size: 13px; }
    .section-title {
      display: flex; justify-content: space-between; align-items: end; gap: 10px;
      margin-bottom: 16px;
    }
    .section-title h2 {
      margin: 0; font-size: 22px; letter-spacing: -.01em;
    }
    .section-title p { margin: 0; color: var(--muted); font-size: 13px; }
    .tutorial-grid {
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px;
    }
    .tutorial-card, .flow-card {
      border-radius: 20px;
      border: 1px solid var(--line);
      background: rgba(34,197,94,.05);
      padding: 18px;
    }
    .step-num {
      width: 36px; height: 36px; border-radius: 999px;
      display: inline-flex; align-items: center; justify-content: center;
      background: linear-gradient(135deg, var(--accent), #86efac);
      color: #052014; font-weight: 800; margin-bottom: 14px;
    }
    .tutorial-card h3, .flow-node h3 { margin: 0 0 10px; font-size: 17px; }
    .tutorial-card p, .flow-card p, .flow-node p { margin: 0; color: var(--muted); line-height: 1.7; font-size: 14px; }
    .guide-list {
      margin: 12px 0 0; padding: 0; list-style: none; display: grid; gap: 10px;
    }
    .guide-list li {
      padding: 10px 12px; border-radius: 14px;
      background: rgba(34,197,94,.06); border: 1px solid var(--line);
      color: #234436; font-size: 14px; line-height: 1.6;
    }
    .flow-track {
      display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px;
      align-items: stretch;
    }
    .flow-node {
      position: relative;
      padding: 18px 16px 16px;
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(255,255,255,.90), rgba(242, 251, 245, .96));
      border: 1px solid var(--line);
      min-height: 154px;
    }
    .flow-node::after {
      content: "→";
      position: absolute;
      right: -14px;
      top: 50%;
      transform: translateY(-50%);
      color: rgba(22, 48, 31, .48);
      font-size: 18px;
      display: none;
    }
    .flow-node:not(:last-child)::after { display: block; }
    .flow-kicker {
      display: inline-flex; align-items: center; gap: 6px;
      font-size: 12px; color: #14532d; margin-bottom: 12px;
      padding: 6px 10px; border-radius: 999px; background: rgba(34, 197, 94, .12); border: 1px solid rgba(34, 197, 94, .22);
    }
    .upload-layout { display: grid; grid-template-columns: 1.05fr .95fr; gap: 18px; }
    .preview-pane, .form-pane {
      border-radius: 22px; border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,.92), rgba(244, 251, 246, .94));
      padding: 20px;
    }
    .preview-shell {
      min-height: 420px; border-radius: 20px;
      border: 1px dashed rgba(34, 197, 94, .28);
      background:
        radial-gradient(circle at top right, rgba(132, 204, 22, .12), transparent 22%),
        linear-gradient(180deg, rgba(248, 253, 249, .96), rgba(236, 248, 239, .94));
      padding: 18px;
    }
    .preview-shell h3 { margin: 0 0 10px; font-size: 18px; }
    .preview-state { color: var(--muted); font-size: 13px; margin-bottom: 14px; }
    .image-view {
      width: 100%; border-radius: 18px; overflow: hidden;
      border: 1px solid rgba(34, 197, 94, .16);
      background: rgba(255,255,255,.72);
    }
    .image-view img { display: block; width: 100%; height: auto; }
    .upload-box {
      border: 1px solid rgba(34, 197, 94, .20);
      border-radius: 18px;
      padding: 18px;
      background: rgba(34,197,94,.05);
    }
    .upload-box input[type=file], .upload-box input[type=url] {
      width: 100%;
      color: var(--text);
      background: rgba(255,255,255,.82);
      border: 1px solid rgba(34, 197, 94, .18);
      border-radius: 12px;
      padding: 11px 12px;
      outline: none;
    }
    .field-label { display: block; margin: 12px 0 8px; color: #234436; font-size: 13px; }
    .actions { display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; align-items: center; }
    .btn {
      appearance: none; border: 0; border-radius: 14px; padding: 12px 18px;
      background: linear-gradient(135deg, #22c55e, #86efac);
      color: #062011; font-weight: 800; cursor: pointer;
      box-shadow: 0 10px 26px rgba(34, 197, 94, .18);
      transition: transform .18s ease, opacity .18s ease, filter .18s ease;
    }
    .btn:hover { transform: translateY(-1px); }
    .btn.secondary {
      background: linear-gradient(135deg, rgba(255,255,255,.92), rgba(229, 251, 233, .95));
      color: #14532d;
      border: 1px solid rgba(34, 197, 94, .22);
      box-shadow: 0 10px 26px rgba(34, 197, 94, .10);
    }
    .btn:disabled,
    .btn.is-disabled {
      opacity: .45;
      cursor: not-allowed;
      transform: none;
      filter: grayscale(.2);
    }
    .hint { color: var(--muted); font-size: 13px; line-height: 1.6; }
    .meta-line { color: var(--muted); font-size: 13px; margin-top: 10px; line-height: 1.7; }
    .results { margin-top: 20px; }
    .result-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
    .result-card {
      border-radius: 22px; border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(10, 19, 28, .94), rgba(8, 15, 22, .9));
      padding: 20px;
    }
    .result-card h2 { margin: 0 0 14px; font-size: 20px; }
    .summary { white-space: pre-wrap; line-height: 1.85; font-size: 16px; color: #edf6fb; }
    .probs { display: grid; gap: 10px; }
    .prob {
      display: flex; justify-content: space-between; gap: 10px; align-items: center;
      padding: 12px 14px; border-radius: 14px;
      background: rgba(34,197,94,.05); border: 1px solid var(--line);
    }
    .progress-bar {
      height: 8px; border-radius: 999px; margin-top: 8px;
      background: rgba(255,255,255,.07); overflow: hidden;
    }
    .progress-bar > span {
      display: block; height: 100%; border-radius: inherit;
      background: linear-gradient(90deg, #22c55e, #86efac);
    }
    /* 大幅结果区仪表盘 */
    .meter {
      width: 160px; height: 160px; border-radius: 999px; display: inline-grid;
      place-items: center; position: relative; margin: 6px auto 0;
      background: conic-gradient(from -90deg, #22c55e 0deg 144deg, #86efac 144deg 252deg, #16a34a 252deg 360deg);
      box-shadow: 0 18px 40px rgba(2,6,23,.55), inset 0 -6px 20px rgba(2,6,23,.4);
      border: 1px solid rgba(255,255,255,.04);
    }
    .meter .meter-fill { width: 88%; height: 88%; border-radius: 999px; display: grid; place-items: center; background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.01)); }
    .meter .meter-center { text-align: center; color: #ecfeff; font-weight: 800; }
    .meter .meter-center .big { font-size: 28px; line-height: 1; }
    .meter .meter-center .small { font-size: 12px; color: var(--muted); margin-top: 4px; }
    .result-highlight {
      border-radius: 16px; padding: 12px; margin-top: 12px;
      background: linear-gradient(180deg, rgba(34,197,94,.08), rgba(34,197,94,.03));
      border: 1px solid rgba(34,197,94,.14); color: #14532d;
    }
    .result-actions {
      display: flex; justify-content: flex-end; gap: 10px; margin: 6px 0 14px; flex-wrap: wrap;
    }
    .result-actions .btn { padding-inline: 14px; }
    .error {
      margin-top: 18px; padding: 14px 16px; border-radius: 16px;
      background: rgba(220, 38, 38, .08); color: #991b1b;
      border: 1px solid rgba(220, 38, 38, .18);
    }
    .footer { margin-top: 16px; color: var(--muted); font-size: 13px; line-height: 1.7; }
    .section { margin-top: 18px; }
    .callout {
      margin-top: 12px; padding: 14px 16px; border-radius: 16px;
      background: rgba(34, 197, 94, .08); border: 1px solid rgba(34, 197, 94, .18);
      color: #14532d; font-size: 13px; line-height: 1.7;
    }
    @media (max-width: 1100px) {
      .hero, .upload-layout, .result-grid { grid-template-columns: 1fr; }
      .tutorial-grid, .flow-track { grid-template-columns: 1fr; }
      .flow-node::after { display: none; }
    }
    @media (max-width: 700px) {
      .wrap { padding: 16px 12px 34px; }
      .hero-copy, .hero-side, .section, .results { padding: 18px; }
      .hero-copy h1 { font-size: 30px; }
      .stat-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div class="brand">
        <div class="brand-mark">智农</div>
        <div class="brand-copy">
          <strong>农作物病虫害AI智能识别预警系统</strong>
          <span>拍照识别病虫害，有网就能用</span>
        </div>
      </div>
      <div class="nav-links">
        <a href="#home">首页</a>
        <a href="#overview">项目介绍</a>
        <a href="#upload">上传识别</a>
        <a href="#results">识别结果</a>
      </div>
    </div>
    <div class="hero-banner panel" style="margin-bottom:18px;display:flex;align-items:center;justify-content:space-between;padding:20px 26px;">
      <div style="display:flex;gap:18px;align-items:center;"> 
        <div style="width:64px;height:64px;border-radius:12px;background:linear-gradient(135deg,#34d399,#10b981);display:grid;place-items:center;font-weight:900;color:#042014;">智农</div>
        <div>
          <div style="font-size:14px;color:var(--muted)">稻花香里说丰年 · 农作物病虫害AI智能识别预警系统</div>
          <div style="font-size:20px;font-weight:800">拍照识别病虫害，一秒看到结果</div>
        </div>
      </div>
      <div style="display:flex;gap:12px;align-items:center">
        <button class="btn" onclick="document.getElementById('image_input').click();">上传图片</button>
        <a href="#upload" class="btn secondary" style="text-decoration:none;color:inherit">开始识别</a>
      </div>
    </div>
    <div class="hero" id="home">
      <div class="panel hero-copy">
        <div class="eyebrow">一句话介绍：拍照识别病虫害</div>
        <h1>让农作物叶片自己说话</h1>
        <p>农民伯伯只需要给庄稼叶子拍张照片，系统就能识别出农作物的病虫害种类，给出防治建议，并把结果整理成便于汇报的预警信息。这个页面保留了智农式的展示结构，同时兼顾本地上传、URL 预览和模型推理。</p>
        <div class="hero-highlights">
          <span class="chip">拍照、上传、一秒识别</span>
          <span class="chip">有网就能用</span>
          <span class="chip">支持 JPG / PNG / BMP</span>
          <span class="chip">多任务联合学习</span>
        </div>
      </div>
      <div class="panel hero-side">
        <div class="side-card">
          <div class="section-title" style="margin-bottom: 10px;">
            <h2>如何使用“智农”</h2>
            <p>有网就能用</p>
          </div>
          <ul class="guide-list">
            <li>网页端直接上传图片，或者粘贴公开图片 URL。</li>
            <li>先生成预览缩略图，确认内容无误后再开始评估。</li>
            <li>查看识别结果、严重程度、风险评分和处理建议。</li>
          </ul>
        </div>
        <div class="side-card">
          <div class="section-title" style="margin-bottom: 12px;">
            <h2>应用场景</h2>
            <p>展示与汇报</p>
          </div>
          <div class="stat-grid">
            <div class="stat"><strong>网页</strong><span>只要有网就能用</span></div>
            <div class="stat"><strong>辅助</strong><span>专家与农户都能看</span></div>
            <div class="stat"><strong>预警</strong><span>结果可用于整理报告</span></div>
          </div>
        </div>
      </div>
    </div>

    <div class="panel section" style="padding: 0; overflow: hidden;">
      <div style="display:grid; grid-template-columns: 1.05fr .95fr; min-height: 340px;">
        <div style="padding: 28px; display:flex; flex-direction:column; justify-content:center; gap: 18px; background: linear-gradient(135deg, rgba(34,197,94,.10), rgba(255,255,255,0));">
          <div class="eyebrow" style="width: fit-content;">项目官网式介绍区</div>
          <h2 style="margin:0; font-size: clamp(28px, 3.4vw, 44px); line-height: 1.08;">把农业病害识别做成一页清晰、可演示、可汇报的产品页面</h2>
          <p style="margin:0; color: var(--muted); line-height: 1.9; font-size: 16px; max-width: 60ch;">这个首页沿用 EasyFarming 那种“问题背景 - 使用方式 - 应用场景 - 黑科技 - 结果展示”的叙事节奏，但用你当前项目的模型和接口来落地。页面本身已经可以作为答辩、项目展示或课程汇报的首页。</p>
          <div class="hero-highlights" style="margin-top: 0;">
            <span class="chip">首页叙事</span>
            <span class="chip">项目介绍</span>
            <span class="chip">识别入口</span>
            <span class="chip">结果预警</span>
          </div>
        </div>
        <div style="padding: 20px; display:grid; place-items:center; background:
          radial-gradient(circle at 25% 20%, rgba(34,197,94,.16), transparent 18%),
          radial-gradient(circle at 76% 26%, rgba(132,204,22,.16), transparent 18%),
          linear-gradient(180deg, rgba(245,253,247,.95), rgba(232,247,236,.92));">
          <div style="width: min(100%, 360px); border-radius: 30px; padding: 18px; border: 1px solid rgba(34,197,94,.16); background: rgba(255,255,255,.78); box-shadow: 0 24px 60px rgba(34, 197, 94, .14);">
            <div style="border-radius: 24px; overflow: hidden; min-height: 260px; background: linear-gradient(160deg, #dcfce7, #bbf7d0 48%, #fef9c3);
              display:grid; place-items:center; position:relative;">
              <div style="position:absolute; inset: 18px; border: 2px dashed rgba(21,128,61,.28); border-radius: 20px;"></div>
              <div style="text-align:center; color:#14532d; padding: 20px; max-width: 240px;">
                <div style="font-size: 44px; line-height: 1; margin-bottom: 10px;">🌱</div>
                <div style="font-size: 18px; font-weight: 800; margin-bottom: 8px;">农田数据看板</div>
                <div style="font-size: 13px; line-height: 1.7; color:#4b6a57;">绿色系主视觉，突出农业、预警、识别和汇报感。</div>
              </div>
            </div>
            <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 12px;">
              <div class="stat"><strong>识别</strong><span>病虫害种类</span></div>
              <div class="stat"><strong>预警</strong><span>风险评分</span></div>
              <div class="stat"><strong>汇报</strong><span>结果图下载</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="panel section" id="overview">
      <div class="section-title">
        <h2>项目速览</h2>
        <p>把 EasyFarming 的展示结构放到这个页面里</p>
      </div>
      <div class="tutorial-grid">
        <div class="tutorial-card">
          <div class="step-num">1</div>
          <h3>一句话介绍</h3>
          <p>给庄稼叶子拍张照片，系统自动识别病虫害，并输出防治建议。</p>
        </div>
        <div class="tutorial-card">
          <div class="step-num">2</div>
          <h3>如何使用</h3>
          <p>网页、App、微信小程序都可以扩展成统一入口，打开即用，用完即走。</p>
        </div>
        <div class="tutorial-card">
          <div class="step-num">3</div>
          <h3>应用场景</h3>
          <p>拍照识别、作物病害早预警、农药化肥精准投放、宏观农业数据采集。</p>
        </div>
        <div class="tutorial-card">
          <div class="step-num">4</div>
          <h3>黑科技</h3>
          <p>基于深度残差网络和多任务学习，把分类、严重程度和风险评估串成一个流程。</p>
        </div>
      </div>
    </div>

    <div class="panel section" id="upload">
      <div class="section-title">
        <h2>完整链路</h2>
        <p>从图片到预警的四步流程</p>
      </div>
      <div class="flow-track">
        <div class="flow-node">
          <div class="flow-kicker">Step 01</div>
          <h3>拍照或上传</h3>
          <p>选择本地图片，或者输入公开图片 URL 作为识别入口。</p>
        </div>
        <div class="flow-node">
          <div class="flow-kicker">Step 02</div>
          <h3>先做预览</h3>
          <p>系统先生成缩略图，确认内容正确后再启动推理。</p>
        </div>
        <div class="flow-node">
          <div class="flow-kicker">Step 03</div>
          <h3>模型判断</h3>
          <p>调用多任务模型，输出病害风险、严重程度与建议摘要。</p>
        </div>
        <div class="flow-node">
          <div class="flow-kicker">Step 04</div>
          <h3>生成报告</h3>
          <p>保存结果图与 JSON 报告，方便汇报、展示和复查。</p>
        </div>
      </div>
    </div>

    <div class="panel section">
      <div class="section-title">
        <h2>上传与预览</h2>
        <p>先确认图片，再进入模型识别</p>
      </div>
      <div class="upload-layout">
        <div class="preview-pane">
          <div class="preview-shell">
            <h3>图片预览</h3>
            <div class="preview-state" id="preview_status">等待上传或输入 URL</div>
            <div class="image-view" id="preview_card" {% if not preview_b64 %}style="display:none;"{% endif %}>
              <img id="preview_img" src="{% if preview_b64 %}data:image/png;base64,{{ preview_b64 }}{% endif %}" alt="预览图">
            </div>
            <div class="callout">提示：如果是本地图片，选择文件后会自动生成缩略图；如果是 URL，请先点“预览”，确认后再开始识别。</div>
          </div>
        </div>
        <div class="form-pane">
          <form method="post" enctype="multipart/form-data" id="upload_form">
            <div class="upload-box">
              <label class="field-label">1. 选择本地图片</label>
              <input type="file" name="image" accept="image/*" id="image_input">
              <label class="field-label">2. 或输入图片 URL</label>
              <input type="url" name="image_url" id="image_url" placeholder="https://example.com/image.jpg">
              <input type="hidden" name="preview_b64" id="preview_b64" value="{{ preview_b64 or '' }}">
              <div class="actions">
                <button class="btn secondary" type="submit" name="action" value="preview">预览</button>
                <button class="btn" type="submit" name="action" value="predict" id="predict_btn" {% if not preview_b64 %}disabled{% endif %}>开始识别</button>
                <span class="hint">评估按钮会在预览成功后自动解锁，避免直接处理未确认文件。</span>
              </div>
              <div class="meta-line">提示：使用的后端模型为 <strong>best_multitask_model.pth</strong>，推理时会自动做 128×128 归一化预处理。</div>
            </div>
          </form>
        </div>
      </div>
    </div>

    {% if result %}
    <div class="panel results" id="results">
      <div class="section-title">
        <h2>识别结果与预警建议</h2>
        <p>模型反馈与概率分布</p>
      </div>
      <div class="result-actions">
        <button class="btn secondary" id="copy_summary_btn" onclick="copySummary();">复制摘要</button>
        <button class="btn secondary" id="share_btn" onclick="shareResult();">分享结果</button>
        <button class="btn secondary" id="download_json_btn" onclick="downloadReport();">下载报告</button>
        <button class="btn" id="download_img_btn" onclick="downloadAnnotated();">下载结果图</button>
      </div>
      <div class="result-grid">
        <div class="result-card">
          <h2>模型反馈图</h2>
          <div class="image-view">
            <img src="data:image/png;base64,{{ result.annotated_image }}" alt="评估结果图">
          </div>
        </div>
        <div class="result-card">
          <div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap;">
            <div style="flex:0 0 180px;text-align:center;">
              <div class="meter" id="disease_meter" data-percent="{{ '%.0f'|format(result.meta.disease_risk_percent) }}">
                <div class="meter-fill">
                  <div class="meter-center">
                    <div class="big">{{ '%.0f'|format(result.meta.disease_risk_percent) }}%</div>
                    <div class="small">病害风险评分</div>
                  </div>
                </div>
              </div>
              <div class="result-highlight">严重程度：<strong style="margin-left:8px;color:#fff">{{ result.meta.severity }}</strong></div>
            </div>
            <div style="flex:1 1 360px;">
              <h2>评估摘要</h2>
              <div class="summary">{{ result.summary }}</div>
              <h2 style="margin-top: 18px;">严重程度概率</h2>
              <div class="probs">
                {% for name, value in result.probabilities.items() %}
                <div class="prob">
                  <span>{{ name }}</span>
                  <strong>{{ '%.1f%%'|format(value * 100) }}</strong>
                </div>
                <div class="progress-bar"><span style="width: {{ '%.0f'|format(value * 100) }}%;"></span></div>
                {% endfor %}
              </div>
              <h2 style="margin-top: 18px;">运行信息</h2>
              <div class="meta-line">
                设备：{{ result.meta.device }}<br>
                置信度：{{ '%.2f'|format(result.meta.severity_confidence * 100) }}%<br>
                模型权重：<code>best_multitask_model.pth</code>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    {% endif %}

    {% if error %}
    <div class="error">{{ error }}</div>
    {% endif %}
  </div>

  <script>
    (function() {
      const form = document.getElementById('upload_form');
      const fileInput = document.getElementById('image_input');
      const urlInput = document.getElementById('image_url');
      const previewField = document.getElementById('preview_b64');
      const previewImg = document.getElementById('preview_img');
      const previewCard = document.getElementById('preview_card');
      const previewStatus = document.getElementById('preview_status');
      const predictBtn = document.getElementById('predict_btn');

      function setPredictLocked(locked) {
        predictBtn.disabled = locked;
        predictBtn.classList.toggle('is-disabled', locked);
      }

      function setPreview(src, label) {
        previewImg.src = src;
        previewCard.style.display = 'block';
        previewStatus.textContent = label;
        previewField.value = src.startsWith('data:') ? src.split(',')[1] : src;
        setPredictLocked(false);
      }

      function clearPreview(lock = true) {
        previewField.value = '';
        previewImg.removeAttribute('src');
        previewCard.style.display = 'none';
        previewStatus.textContent = '等待上传或输入 URL';
        if (lock) setPredictLocked(true);
      }

      if (fileInput) {
        fileInput.addEventListener('change', function() {
          const file = fileInput.files && fileInput.files[0];
          if (!file) {
            clearPreview();
            return;
          }
          const reader = new FileReader();
          reader.onload = function() {
            setPreview(reader.result, '本地缩略图已生成，评估按钮已解锁');
          };
          reader.readAsDataURL(file);
          if (urlInput.value.trim()) urlInput.value = '';
        });
      }

      if (urlInput) {
        urlInput.addEventListener('input', function() {
          if (urlInput.value.trim()) {
            clearPreview();
          }
        });
      }

      if (form) {
        form.addEventListener('submit', function(ev) {
          const action = ev.submitter && ev.submitter.value ? ev.submitter.value : 'preview';
          if (action === 'predict' && !previewField.value.trim()) {
            ev.preventDefault();
            previewStatus.textContent = '请先预览成功，再开始评估。';
          }
        });
      }

      window.addEventListener('DOMContentLoaded', function() {
        if (previewField.value.trim()) {
          if (previewField.value.startsWith('data:')) {
            previewImg.src = previewField.value;
          } else {
            previewImg.src = 'data:image/png;base64,' + previewField.value;
          }
          previewCard.style.display = 'block';
          previewStatus.textContent = '预览已就绪，评估按钮已解锁';
          setPredictLocked(false);
        } else {
          setPredictLocked(true);
        }
        // animate meter if exists
        try {
          function meterClass(value) {
            if (value < 40) return '健康';
            if (value < 70) return '警告';
            return '高风险';
          }

          function buildMeterGradient(value) {
            const greenEnd = 40;
            const warnEnd = 70;
            const clamped = Math.max(0, Math.min(100, value));
            const greenDeg = Math.min(clamped, greenEnd) * 3.6;
            const warnDeg = Math.min(clamped, warnEnd) * 3.6;
            const endDeg = clamped * 3.6;
            return `conic-gradient(from -90deg, #22c55e 0deg ${greenDeg}deg, #f59e0b ${greenDeg}deg ${warnDeg}deg, #ef4444 ${warnDeg}deg ${endDeg}deg, rgba(255,255,255,0.06) ${endDeg}deg 360deg)`;
          }

          function animateMeters() {
            document.querySelectorAll('.meter[data-percent]').forEach(el => {
              const target = Number(el.getAttribute('data-percent')) || 0;
              let start = null;
              const duration = 1200;
              const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
              function step(ts) {
                if (!start) start = ts;
                const t = Math.min(1, (ts - start) / duration);
                const current = Math.round(easeOutCubic(t) * target);
                el.style.background = buildMeterGradient(current);
                const text = el.querySelector('.big');
                if (text) text.textContent = current + '%';
                if (t < 1) requestAnimationFrame(step);
              }
              requestAnimationFrame(step);
            });
          }
          animateMeters();
        } catch (e) { console.warn('meter animate failed', e); }

        window.copySummary = async function() {
          try {
            const report = buildShareText();
            if (navigator.clipboard && navigator.clipboard.writeText) {
              await navigator.clipboard.writeText(report);
            } else {
              const ta = document.createElement('textarea');
              ta.value = report;
              document.body.appendChild(ta);
              ta.select();
              document.execCommand('copy');
              ta.remove();
            }
            alert('摘要已复制');
          } catch (e) { console.warn(e); alert('复制失败'); }
        }

        window.shareResult = async function() {
          try {
            const text = buildShareText();
            const url = window.location.href;
            if (navigator.share) {
              await navigator.share({ title: '植物病害图片评估结果', text, url });
            } else {
              await navigator.clipboard.writeText(text + '\n' + url);
              alert('当前浏览器不支持原生分享，已复制分享文案');
            }
          } catch (e) { console.warn(e); alert('分享失败'); }
        }

        function buildShareText() {
          const summaryEl = document.querySelector('.summary');
          const metaEl = document.querySelector('.meta-line');
          const meterEl = document.querySelector('.meter .meter-center .big');
          const severityEl = document.querySelector('.result-highlight strong');
          const title = '植物病害图片评估结果';
          const score = meterEl ? meterEl.textContent.trim() : '';
          const severity = severityEl ? severityEl.textContent.trim() : '';
          return [
            title,
            score ? `病害风险评分：${score}` : '',
            severity ? `严重程度：${severity}` : '',
            summaryEl ? summaryEl.textContent.trim() : '',
            metaEl ? metaEl.textContent.trim().replace(/\s+/g, ' ') : ''
          ].filter(Boolean).join('\n');
        }

        // download helpers for result actions
        window.downloadAnnotated = function() {
          try {
            const img = document.querySelector('.panel.results img');
            if (!img || !img.src) { alert('未找到结果图像'); return; }
            const a = document.createElement('a');
            a.href = img.src;
            a.download = 'evaluation_result.png';
            document.body.appendChild(a);
            a.click();
            a.remove();
          } catch (e) { console.warn(e); alert('下载失败'); }
        }

        window.downloadReport = function() {
          try {
            const summaryEl = document.querySelector('.summary');
            const metaEl = document.querySelector('.meta-line');
            const probsEls = document.querySelectorAll('.probs .prob');
            const probs = {};
            probsEls.forEach(p => {
              const key = p.querySelector('span') && p.querySelector('span').textContent.trim();
              const val = p.querySelector('strong') && p.querySelector('strong').textContent.trim();
              if (key) probs[key] = val;
            });
            const img = document.querySelector('.panel.results img');
            const report = {
              summary: summaryEl ? summaryEl.textContent.trim() : '',
              meta: metaEl ? metaEl.textContent.trim() : '',
              probabilities: probs,
              annotated_image: img ? img.src : null,
            };
            const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = 'evaluation_report.json';
            document.body.appendChild(a); a.click(); a.remove();
            URL.revokeObjectURL(url);
          } catch (e) { console.warn(e); alert('导出报告失败'); }
        }
      });
    })();
  </script>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
  result = None
  error = None
  preview_b64 = None
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
        else:
          # predict
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
        import traceback

        traceback.print_exc()
        if debug_path:
          error = f"图片处理失败：{exc} (已保存原始上传为: {debug_path})"
        else:
          error = f"图片处理失败：{exc}"

  return render_template("index.html", result=result, error=error, preview_b64=preview_b64)


@app.route('/reports/<path:fname>')
def download_report(fname):
  reports_dir = os.path.join(os.getcwd(), 'reports')
  if not os.path.exists(os.path.join(reports_dir, fname)):
    return ('Not found', 404)
  return send_from_directory(reports_dir, fname, as_attachment=True)


if __name__ == "__main__":
  host = os.environ.get("APP_HOST", "0.0.0.0")
  port = int(os.environ.get("APP_PORT", "7860"))
  app.run(host=host, port=port, debug=False)