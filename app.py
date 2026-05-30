import base64
import io
import requests
import socket
from urllib.parse import urlparse
import os

from flask import Flask, render_template_string, request
from PIL import Image

from scripts.inference_utils import predict_image


app = Flask(__name__)


HTML = r"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>植物病害图片评估</title>
  <style>
    :root {
      --bg0: #071018;
      --bg1: #0b1b24;
      --bg2: #102532;
      --card: rgba(8, 16, 24, 0.82);
      --card2: rgba(10, 24, 34, 0.88);
      --line: rgba(148, 163, 184, 0.18);
      --line-strong: rgba(56, 189, 148, 0.24);
      --text: #e8f1f6;
      --muted: #9fb0bd;
      --accent: #34d399;
      --accent-2: #f59e0b;
      --danger: #fb7185;
      --shadow: 0 24px 70px rgba(0, 0, 0, .34);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      color: var(--text);
      font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
      background:
        radial-gradient(circle at 15% 20%, rgba(52, 211, 153, .18), transparent 26%),
        radial-gradient(circle at 86% 10%, rgba(245, 158, 11, .10), transparent 22%),
        radial-gradient(circle at 82% 78%, rgba(56, 189, 248, .08), transparent 24%),
        linear-gradient(180deg, var(--bg0), var(--bg1) 45%, var(--bg2));
      min-height: 100vh;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: .16;
      background-image:
        linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);
      background-size: 38px 38px;
      mask-image: linear-gradient(180deg, rgba(0,0,0,.8), transparent 90%);
    }
    .wrap { max-width: 1320px; margin: 0 auto; padding: 28px 18px 56px; position: relative; }
    .hero {
      display: grid;
      grid-template-columns: 1.08fr .92fr;
      gap: 20px;
      margin-bottom: 20px;
      align-items: stretch;
    }
    .panel {
      background: linear-gradient(180deg, rgba(12, 24, 34, .88), rgba(7, 17, 25, .84));
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
    }
    .hero-copy, .hero-side, .section, .results { padding: 26px; }
    .eyebrow {
      display: inline-flex; align-items: center; gap: 8px;
      padding: 8px 14px; border-radius: 999px;
      color: #dcfce7; background: rgba(52, 211, 153, .10);
      border: 1px solid rgba(52, 211, 153, .22); font-size: 13px; letter-spacing: .2px;
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
      background: rgba(255,255,255,.04);
      color: #dce6eb; font-size: 13px;
    }
    .hero-side {
      display: grid; gap: 16px;
      grid-template-rows: auto 1fr;
    }
    .side-card {
      border-radius: 20px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(14, 30, 42, .76), rgba(8, 18, 26, .78));
      padding: 18px;
    }
    .stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 14px; }
    .stat {
      padding: 14px 12px; border-radius: 16px;
      background: rgba(255,255,255,.03);
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
      background: rgba(255,255,255,.03);
      padding: 18px;
    }
    .step-num {
      width: 36px; height: 36px; border-radius: 999px;
      display: inline-flex; align-items: center; justify-content: center;
      background: linear-gradient(135deg, var(--accent), #12b981);
      color: #052014; font-weight: 800; margin-bottom: 14px;
    }
    .tutorial-card h3, .flow-node h3 { margin: 0 0 10px; font-size: 17px; }
    .tutorial-card p, .flow-card p, .flow-node p { margin: 0; color: var(--muted); line-height: 1.7; font-size: 14px; }
    .guide-list {
      margin: 12px 0 0; padding: 0; list-style: none; display: grid; gap: 10px;
    }
    .guide-list li {
      padding: 10px 12px; border-radius: 14px;
      background: rgba(255,255,255,.03); border: 1px solid var(--line);
      color: #d7e2e8; font-size: 14px; line-height: 1.6;
    }
    .flow-track {
      display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px;
      align-items: stretch;
    }
    .flow-node {
      position: relative;
      padding: 18px 16px 16px;
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(18, 36, 48, .95), rgba(11, 20, 28, .88));
      border: 1px solid var(--line);
      min-height: 154px;
    }
    .flow-node::after {
      content: "→";
      position: absolute;
      right: -14px;
      top: 50%;
      transform: translateY(-50%);
      color: rgba(148, 163, 184, .8);
      font-size: 18px;
      display: none;
    }
    .flow-node:not(:last-child)::after { display: block; }
    .flow-kicker {
      display: inline-flex; align-items: center; gap: 6px;
      font-size: 12px; color: #f8fafc; margin-bottom: 12px;
      padding: 6px 10px; border-radius: 999px; background: rgba(52, 211, 153, .12); border: 1px solid rgba(52, 211, 153, .22);
    }
    .upload-layout { display: grid; grid-template-columns: 1.05fr .95fr; gap: 18px; }
    .preview-pane, .form-pane {
      border-radius: 22px; border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(9, 20, 28, .92), rgba(10, 22, 30, .84));
      padding: 20px;
    }
    .preview-shell {
      min-height: 420px; border-radius: 20px;
      border: 1px dashed rgba(148, 163, 184, .34);
      background:
        radial-gradient(circle at top right, rgba(245, 158, 11, .08), transparent 22%),
        linear-gradient(180deg, rgba(17, 32, 42, .88), rgba(6, 12, 18, .88));
      padding: 18px;
    }
    .preview-shell h3 { margin: 0 0 10px; font-size: 18px; }
    .preview-state { color: var(--muted); font-size: 13px; margin-bottom: 14px; }
    .image-view {
      width: 100%; border-radius: 18px; overflow: hidden;
      border: 1px solid rgba(148, 163, 184, .18);
      background: rgba(255,255,255,.03);
    }
    .image-view img { display: block; width: 100%; height: auto; }
    .upload-box {
      border: 1px solid rgba(148, 163, 184, .22);
      border-radius: 18px;
      padding: 18px;
      background: rgba(255,255,255,.03);
    }
    .upload-box input[type=file], .upload-box input[type=url] {
      width: 100%;
      color: var(--text);
      background: rgba(255,255,255,.04);
      border: 1px solid rgba(148, 163, 184, .22);
      border-radius: 12px;
      padding: 11px 12px;
      outline: none;
    }
    .field-label { display: block; margin: 12px 0 8px; color: #dbe7ee; font-size: 13px; }
    .actions { display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; align-items: center; }
    .btn {
      appearance: none; border: 0; border-radius: 14px; padding: 12px 18px;
      background: linear-gradient(135deg, #34d399, #10b981);
      color: #032016; font-weight: 800; cursor: pointer;
      box-shadow: 0 10px 26px rgba(16, 185, 129, .22);
      transition: transform .18s ease, opacity .18s ease, filter .18s ease;
    }
    .btn:hover { transform: translateY(-1px); }
    .btn.secondary {
      background: linear-gradient(135deg, rgba(245, 158, 11, .98), rgba(249, 115, 22, .98));
      color: #1b1202;
      box-shadow: 0 10px 26px rgba(245, 158, 11, .18);
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
      background: rgba(255,255,255,.04); border: 1px solid var(--line);
    }
    .progress-bar {
      height: 8px; border-radius: 999px; margin-top: 8px;
      background: rgba(255,255,255,.07); overflow: hidden;
    }
    .progress-bar > span {
      display: block; height: 100%; border-radius: inherit;
      background: linear-gradient(90deg, #34d399, #f59e0b);
    }
    /* 大幅结果区仪表盘 */
    .meter {
      width: 160px; height: 160px; border-radius: 999px; display: inline-grid;
      place-items: center; position: relative; margin: 6px auto 0;
      background: conic-gradient(from -90deg, #22c55e 0deg 144deg, #f59e0b 144deg 252deg, #ef4444 252deg 360deg);
      box-shadow: 0 18px 40px rgba(2,6,23,.55), inset 0 -6px 20px rgba(2,6,23,.4);
      border: 1px solid rgba(255,255,255,.04);
    }
    .meter .meter-fill { width: 88%; height: 88%; border-radius: 999px; display: grid; place-items: center; background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.01)); }
    .meter .meter-center { text-align: center; color: #ecfeff; font-weight: 800; }
    .meter .meter-center .big { font-size: 28px; line-height: 1; }
    .meter .meter-center .small { font-size: 12px; color: var(--muted); margin-top: 4px; }
    .result-highlight {
      border-radius: 16px; padding: 12px; margin-top: 12px;
      background: linear-gradient(180deg, rgba(52,211,153,.06), rgba(52,211,153,.02));
      border: 1px solid rgba(52,211,153,.08); color: #e8fff7;
    }
    .result-actions {
      display: flex; justify-content: flex-end; gap: 10px; margin: 6px 0 14px; flex-wrap: wrap;
    }
    .result-actions .btn { padding-inline: 14px; }
    .error {
      margin-top: 18px; padding: 14px 16px; border-radius: 16px;
      background: rgba(251, 113, 133, .12); color: #fecdd3;
      border: 1px solid rgba(251, 113, 133, .24);
    }
    .footer { margin-top: 16px; color: var(--muted); font-size: 13px; line-height: 1.7; }
    .section { margin-top: 18px; }
    .callout {
      margin-top: 12px; padding: 14px 16px; border-radius: 16px;
      background: rgba(52, 211, 153, .08); border: 1px solid rgba(52, 211, 153, .18);
      color: #d6ffee; font-size: 13px; line-height: 1.7;
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
    <div class="hero-banner panel" style="margin-bottom:18px;display:flex;align-items:center;justify-content:space-between;padding:20px 26px;">
      <div style="display:flex;gap:18px;align-items:center;"> 
        <div style="width:64px;height:64px;border-radius:12px;background:linear-gradient(135deg,#34d399,#10b981);display:grid;place-items:center;font-weight:900;color:#042014;">PV</div>
        <div>
          <div style="font-size:14px;color:var(--muted)">演示版 · PlantVillage</div>
          <div style="font-size:20px;font-weight:800">交互式病害评估演示页面</div>
        </div>
      </div>
      <div style="display:flex;gap:12px;align-items:center">
        <button class="btn" onclick="document.getElementById('image_input').click();">上传图片</button>
        <a href="#upload" class="btn secondary" style="text-decoration:none;color:inherit">查看流程</a>
      </div>
    </div>
    <div class="hero">
      <div class="panel hero-copy">
        <div class="eyebrow">PlantVillage / 叶片病害评估 · 先预览再评估</div>
        <h1>植物病害图片评估界面</h1>
        <p>上传本地图片或输入公开图片 URL，先生成缩略图并确认内容，再开始模型评估。页面会返回病害风险评分、严重程度判断和处理建议，适合演示、汇报和课堂讲解。</p>
        <div class="hero-highlights">
          <span class="chip">自动缩略图预览</span>
          <span class="chip">预览成功后才能评估</span>
          <span class="chip">支持 JPG / PNG / BMP</span>
          <span class="chip">多任务模型输出</span>
        </div>
      </div>
      <div class="panel hero-side">
        <div class="side-card">
          <div class="section-title" style="margin-bottom: 10px;">
            <h2>新手教程</h2>
            <p>3 分钟上手</p>
          </div>
          <ul class="guide-list">
            <li>第一步：选择一张本地叶片图片，或者粘贴公开图片 URL。</li>
            <li>第二步：系统会自动生成缩略图，确认无误后再进入评估。</li>
            <li>第三步：查看模型反馈图、风险分数、严重程度与处理建议。</li>
          </ul>
        </div>
        <div class="side-card">
          <div class="section-title" style="margin-bottom: 12px;">
            <h2>核心特点</h2>
            <p>更像产品页</p>
          </div>
          <div class="stat-grid">
            <div class="stat"><strong>2 步</strong><span>预览后评估</span></div>
            <div class="stat"><strong>1 次</strong><span>上传即可复用</span></div>
            <div class="stat"><strong>3 类</strong><span>严重程度输出</span></div>
          </div>
        </div>
      </div>
    </div>

    <div class="panel section">
      <div class="section-title">
        <h2>流程图</h2>
        <p>从上传到反馈的完整链路</p>
      </div>
      <div class="flow-track">
        <div class="flow-node">
          <div class="flow-kicker">Step 01</div>
          <h3>选择图片</h3>
          <p>本地上传或粘贴 URL，系统接收原始图片输入。</p>
        </div>
        <div class="flow-node">
          <div class="flow-kicker">Step 02</div>
          <h3>自动预览</h3>
          <p>先生成缩略图，避免把错误文件直接送入模型。</p>
        </div>
        <div class="flow-node">
          <div class="flow-kicker">Step 03</div>
          <h3>确认内容</h3>
          <p>预览成功后，评估按钮自动解锁，确保流程可控。</p>
        </div>
        <div class="flow-node">
          <div class="flow-kicker">Step 04</div>
          <h3>模型推理</h3>
          <p>调用训练好的多任务模型，生成风险、严重程度和建议。</p>
        </div>
        <div class="flow-node">
          <div class="flow-kicker">Step 05</div>
          <h3>输出汇报</h3>
          <p>展示结果图和概率分布，适合答辩和展示。</p>
        </div>
      </div>
    </div>

    <div class="panel section">
      <div class="section-title">
        <h2>上传与预览</h2>
        <p>先看到缩略图，再进行模型评估</p>
      </div>
      <div class="upload-layout">
        <div class="preview-pane">
          <div class="preview-shell">
            <h3>图片预览</h3>
            <div class="preview-state" id="preview_status">等待上传或输入 URL</div>
            <div class="image-view" id="preview_card" {% if not preview_b64 %}style="display:none;"{% endif %}>
              <img id="preview_img" src="{% if preview_b64 %}data:image/png;base64,{{ preview_b64 }}{% endif %}" alt="预览图">
            </div>
            <div class="callout">提示：如果是本地图片，选择文件后会自动生成缩略图；如果是 URL，请先点“预览”，确认后再开始评估。</div>
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
                <button class="btn" type="submit" name="action" value="predict" id="predict_btn" {% if not preview_b64 %}disabled{% endif %}>开始评估</button>
                <span class="hint">评估按钮会在预览成功后自动解锁，避免直接处理未确认文件。</span>
              </div>
              <div class="meta-line">提示：使用的后端模型为 <strong>best_multitask_model.pth</strong>，推理时会自动做 128×128 归一化预处理。</div>
            </div>
          </form>
        </div>
      </div>
    </div>

    {% if result %}
    <div class="panel results">
      <div class="section-title">
        <h2>评估结果</h2>
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
      if host.startswith("127.") or host.startswith("localhost") or host.startswith("10.") or host.startswith("192.168") or host.startswith("172."):
        raise ValueError("拒绝下载内网或本地地址")
      try:
        resp = requests.get(image_url, timeout=6, stream=True)
        resp.raise_for_status()
      except Exception as re:
        raise ValueError(f"无法下载图片: {re}")
      cl = resp.headers.get("Content-Length")
      max_bytes = 5 * 1024 * 1024
      if cl and int(cl) > max_bytes:
        raise ValueError("图片太大，最大支持 5MB")
      return resp.content
    else:
      data = file.read()
      return data

  def _decode_bytes_to_image(data):
    nonlocal debug_path
    if not data:
      raise ValueError("上传文件为空")
    prefix = (data[:40] or b"").lower()
    if prefix.startswith(b"[internetshortcut]") or b"url=" in prefix or prefix.startswith(b"http"):
      raise ValueError("检测到上传内容像是链接/快捷方式 (.url)，不是图片。请在浏览器中右键图片->另存为，然后再上传本地图片。")

    try:
      image = Image.open(io.BytesIO(data))
      image.load()
      return image.convert("RGB")
    except Exception as e1:
      print(f"[UPLOAD] PIL.from bytes failed: {e1}")
      try:
        import cv2
        import numpy as np

        arr = np.frombuffer(data, dtype=np.uint8)
        decoded = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if decoded is None:
          raise ValueError("cv2.imdecode returned None")
        decoded = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
        return Image.fromarray(decoded).convert("RGB")
      except Exception:
        debug_path = os.path.join(os.getcwd(), f"upload_debug_{int(os.getpid())}.bin")
        with open(debug_path, "wb") as fh:
          fh.write(data)
        print(f"[UPLOAD] saved raw upload to: {debug_path}")
        raise

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
    return Image.open(io.BytesIO(base64.b64decode(normalized))).convert("RGB")

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
            print(f"[UPLOAD] preview bytes={len(data) if data is not None else 'None'}")
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

          annotated, summary, probabilities, meta = predict_image(image)
          buffer = io.BytesIO()
          annotated.save(buffer, format="PNG")
          annotated_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
          result = {
            "annotated_image": annotated_b64,
            "summary": summary,
            "probabilities": probabilities,
            "meta": meta,
          }
      except Exception as exc:
        import traceback

        traceback.print_exc()
        if debug_path:
          error = f"图片处理失败：{exc} (已保存原始上传为: {debug_path})"
        else:
          error = f"图片处理失败：{exc}"

  return render_template_string(HTML, result=result, error=error, preview_b64=preview_b64)


if __name__ == "__main__":
  host = os.environ.get("APP_HOST", "0.0.0.0")
  port = int(os.environ.get("APP_PORT", "7860"))
  app.run(host=host, port=port, debug=False)