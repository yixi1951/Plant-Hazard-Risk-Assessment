// 智农主页面交互脚本，原本在index.html中的<script>已迁移
(function() {
  const form = document.getElementById('upload_form');
  const fileInput = document.getElementById('image_input');
  const urlInput = document.getElementById('image_url');
  const previewField = document.getElementById('preview_b64');
  const previewImg = document.getElementById('preview_img');
  const previewCard = document.getElementById('preview_card');
  const previewStatus = document.getElementById('preview_status');
  const predictBtn = document.getElementById('predict_btn');
  const uploadProgress = document.getElementById('upload_progress');
  const uploadProgressBar = document.getElementById('upload_progress_bar');
  const uploadProgressText = document.getElementById('upload_progress_text');

  function setPredictLocked(locked) {
    if (!predictBtn) return;
    predictBtn.disabled = locked;
    predictBtn.classList.toggle('is-disabled', locked);
  }

  function setPreview(src, label) {
    if (!previewImg || !previewCard) return;
    previewImg.src = src;
    previewCard.style.display = 'block';
    previewStatus.textContent = label;
    previewField.value = src.startsWith('data:') ? src.split(',')[1] : src;
    setPredictLocked(false);
  }

  function clearPreview(lock = true) {
    if (!previewField || !previewImg || !previewCard) return;
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
      if (action === 'predict') {
        ev.preventDefault();
        // send via XHR to monitor upload progress
        const fd = new FormData(form);
        fd.set('action', 'predict');
        const xhr = new XMLHttpRequest();
        xhr.open('POST', window.location.pathname, true);
        xhr.responseType = 'document';

        xhr.upload.onprogress = function(e) {
          if (!e.lengthComputable) return;
          const percent = Math.round((e.loaded / e.total) * 100);
          if (uploadProgress) uploadProgress.style.display = 'block';
          if (uploadProgressBar) uploadProgressBar.value = percent;
          if (uploadProgressText) uploadProgressText.textContent = '上传进度：' + percent + '%';
        };

        xhr.onload = function() {
          // replace page with returned HTML document
          if (xhr.status >= 200 && xhr.status < 300) {
            document.open();
            document.write(xhr.response.documentElement.outerHTML);
            document.close();
          } else {
            alert('上传或评估失败，HTTP ' + xhr.status);
          }
        };

        xhr.onerror = function() { alert('网络错误，上传失败。'); };
        xhr.send(fd);
      } else {
        // let preview submit as normal to server (server-side preview)
      }
    });
  }

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

  window.generateQR = function() {
    try {
      const container = document.getElementById('qr_container');
      if (!container) return;
      const url = window.location.href;
      const api = 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=' + encodeURIComponent(url);
      container.innerHTML = '<img src="' + api + '" alt="QR">';
      container.style.display = 'block';
    } catch (e) { console.warn(e); }
  }

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

  // on load: restore preview state locked/unlocked
  document.addEventListener('DOMContentLoaded', function() {
    if (previewField && previewField.value && previewField.value.trim()) {
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
  });
})();
