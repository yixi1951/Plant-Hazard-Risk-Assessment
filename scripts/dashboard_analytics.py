"""
从 reports/*.json 聚合仪表盘可视化数据。
"""

from __future__ import annotations

import glob
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


def _is_demo_report(obj: dict, basename: str = '') -> bool:
    if obj.get('demo') is True:
        return True
    if (obj.get('meta') or {}).get('demo') is True:
        return True
    if basename.startswith('demo_'):
        return True
    name = basename or ''
    if 'demo_' in name:
        return True
    return False


def _load_report_objects(
    reports_dir: str,
    limit: Optional[int] = None,
    days: Optional[int] = None,
    source_filter: str = 'all',
) -> List[dict]:
    """
    source_filter: all | real | demo
    days: 仅保留 generated_at 在最近 N 天内的报告（None=不限制）
    """
    if not os.path.isdir(reports_dir):
        return []
    files = sorted(
        glob.glob(os.path.join(reports_dir, '*.json')),
        key=os.path.getmtime,
    )
    cutoff = None
    if days is not None and days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)

    out = []
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                obj = json.load(fh)
        except Exception:
            continue
        base = os.path.basename(f)
        is_demo = _is_demo_report(obj, base)
        if source_filter == 'real' and is_demo:
            continue
        if source_filter == 'demo' and not is_demo:
            continue
        if cutoff is not None:
            dt = _parse_report_time(obj, base)
            if dt is None or dt < cutoff:
                continue
        out.append(obj)

    if limit and len(out) > limit:
        out = out[-limit:]
    return out


def _meta(obj: dict) -> dict:
    return obj.get('meta') or {}


def _risk_percent(meta: dict) -> int:
    dr = meta.get('disease_risk_percent')
    if dr is None:
        dr = meta.get('disease_risk') or meta.get('risk_percent') or 50
    try:
        return max(0, min(100, int(float(dr))))
    except Exception:
        return 50


def _confidence_percent(meta: dict) -> int:
    sc = meta.get('severity_confidence')
    if sc is None:
        sc = meta.get('disease_confidence') or meta.get('confidence') or 0.9
    try:
        v = float(sc)
        if v <= 1.0:
            v *= 100
        return max(0, min(100, int(v)))
    except Exception:
        return 90


def _severity_label(meta: dict) -> str:
    s = (meta.get('severity') or '').strip()
    if s in ('健康', '一般', '严重'):
        return s
    if s:
        return s
    r = _risk_percent(meta)
    if r < 40:
        return '健康'
    if r < 70:
        return '一般'
    return '严重'


def _crop_label(meta: dict, obj: dict) -> str:
    c = (meta.get('crop') or '').strip()
    if c:
        return c
    tp = meta.get('treatment_plan') or obj.get('treatment_plan') or {}
    c = (tp.get('crop') or '').strip()
    return c or '未标注'


def _parse_report_time(obj: dict, basename: str) -> Optional[datetime]:
    gen = obj.get('generated_at') or basename
    s = str(gen)
    m = re.search(r'(\d{4})[-/]?(\d{2})[-/]?(\d{2})', s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            pass
    m = re.search(r'(\d{4})(\d{2})(\d{2})', s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except Exception:
            pass
    return None


def build_batch_visualization(results: List[dict]) -> Dict[str, Any]:
    """从 /batch_predict 返回的 results 数组聚合本次批量图表数据。"""
    success = [r for r in results if not r.get('error')]
    fail = len(results) - len(success)
    outcome_pie = [
        {'name': '成功', 'value': len(success)},
        {'name': '失败', 'value': fail},
    ]
    risk_buckets = {'0–40% 健康': 0, '40–70% 一般': 0, '70–100% 高风险': 0}
    disease_counter: Counter = Counter()
    severity_counter: Counter = Counter()
    risks: List[int] = []

    for r in success:
        try:
            risk = int(float(r.get('risk_score') if r.get('risk_score') is not None else 50))
        except Exception:
            risk = 50
        risk = max(0, min(100, risk))
        risks.append(risk)
        if risk < 40:
            risk_buckets['0–40% 健康'] += 1
        elif risk < 70:
            risk_buckets['40–70% 一般'] += 1
        else:
            risk_buckets['70–100% 高风险'] += 1
        name = (r.get('disease_name') or '未知').strip()
        disease_counter[name] += 1
        sev = (r.get('severity') or '').strip()
        if sev in ('健康', '一般', '严重'):
            severity_counter[sev] += 1
        elif sev:
            severity_counter['一般'] += 1

    disease_top = [{'name': k, 'value': v} for k, v in disease_counter.most_common(8)]
    severity_pie = [
        {'name': k, 'value': severity_counter.get(k, 0)}
        for k in ['健康', '一般', '严重']
    ]

    return {
        'total': len(results),
        'success_count': len(success),
        'fail_count': fail,
        'outcome_pie': outcome_pie,
        'risk_distribution': {
            'labels': list(risk_buckets.keys()),
            'values': list(risk_buckets.values()),
        },
        'disease_top': disease_top,
        'severity_pie': severity_pie,
        'avg_risk': round(sum(risks) / len(risks), 1) if risks else None,
    }


def build_visualization_payload(
    reports_dir: str,
    catalog_crop_counts: Optional[Dict[str, int]] = None,
    max_reports: int = 200,
    days: Optional[int] = None,
    source_filter: str = 'all',
) -> Dict[str, Any]:
    """
    返回前端 ECharts 使用的结构化数据。
    catalog_crop_counts: 病害知识库按作物计数（无报告时作演示）。
    days / source_filter: 与 API 查询参数一致。
    """
    objs = _load_report_objects(
        reports_dir,
        limit=max_reports,
        days=days,
        source_filter=source_filter,
    )

    severity_order = ['健康', '一般', '严重']
    severity_counter: Counter = Counter()
    disease_counter: Counter = Counter()
    crop_counter: Counter = Counter()
    risk_buckets = {'0–40% 健康': 0, '40–70% 一般': 0, '70–100% 高风险': 0}
    scatter: List[Dict[str, Any]] = []
    daily_counter: Counter = Counter()
    urgency_counter: Counter = Counter()

    for obj in objs:
        meta = _meta(obj)
        sev = _severity_label(meta)
        severity_counter[sev] += 1
        name = (meta.get('disease_name') or '未知').strip()
        disease_counter[name] += 1
        crop_counter[_crop_label(meta, obj)] += 1
        risk = _risk_percent(meta)
        conf = _confidence_percent(meta)
        if risk < 40:
            risk_buckets['0–40% 健康'] += 1
        elif risk < 70:
            risk_buckets['40–70% 一般'] += 1
        else:
            risk_buckets['70–100% 高风险'] += 1
        scatter.append({
            'name': name,
            'risk': risk,
            'confidence': conf,
            'severity': sev,
        })
        urg = (meta.get('urgency') or (meta.get('treatment_plan') or {}).get('urgency') or '中')
        urgency_counter[str(urg)] += 1
        dt = _parse_report_time(obj, '')
        if dt:
            daily_counter[dt.strftime('%m/%d')] += 1

    # 病害 Top N
    top_n = 8
    disease_top = [
        {'name': k, 'value': v}
        for k, v in disease_counter.most_common(top_n)
    ]

    severity_pie = [
        {'name': k, 'value': severity_counter.get(k, 0)}
        for k in severity_order
    ]
    use_demo_fallback = not objs and source_filter == 'all' and not days
    if sum(p['value'] for p in severity_pie) == 0 and use_demo_fallback:
        severity_pie = [
            {'name': '健康', 'value': 2},
            {'name': '一般', 'value': 3},
            {'name': '严重', 'value': 2},
        ]

    crop_items = [
        {'name': k, 'value': v}
        for k, v in crop_counter.most_common(10)
        if k != '未标注' or v > 0
    ]
    if not crop_items and catalog_crop_counts and use_demo_fallback:
        crop_items = [
            {'name': k, 'value': v}
            for k, v in sorted(catalog_crop_counts.items(), key=lambda x: -x[1])[:10]
        ]

    risk_bar = {
        'labels': list(risk_buckets.keys()),
        'values': list(risk_buckets.values()),
    }
    if sum(risk_bar['values']) == 0 and use_demo_fallback:
        risk_bar = {
            'labels': list(risk_buckets.keys()),
            'values': [3, 2, 2],
        }

    # 按时间排序的最近 14 天活动（有日期的报告）
    if daily_counter:
        labels = sorted(daily_counter.keys(), key=lambda x: tuple(int(p) for p in x.split('/')))
        activity = {
            'labels': labels[-14:],
            'values': [daily_counter[l] for l in labels[-14:]],
        }
    elif use_demo_fallback:
        activity = {
            'labels': ['样例1', '样例2', '样例3', '样例4', '样例5', '样例6', '样例7'],
            'values': [1, 2, 1, 3, 2, 1, 2],
        }
    else:
        activity = {'labels': [], 'values': []}

    urgency_pie = [
        {'name': k, 'value': v}
        for k, v in urgency_counter.most_common()
    ]
    if not urgency_pie and use_demo_fallback:
        urgency_pie = [
            {'name': '低', 'value': 2},
            {'name': '中', 'value': 4},
            {'name': '高', 'value': 1},
        ]

    avg_risk = round(sum(s['risk'] for s in scatter) / len(scatter), 1) if scatter else None
    avg_conf = round(sum(s['confidence'] for s in scatter) / len(scatter), 1) if scatter else None

    return {
        'report_count': len(objs),
        'severity_pie': severity_pie,
        'disease_top': disease_top if disease_top else (
            [
                {'name': '玉米大斑病', 'value': 2},
                {'name': '苹果斑点落叶病', 'value': 1},
            ] if use_demo_fallback else []
        ),
        'crop_distribution': crop_items if crop_items else (
            [
                {'name': '玉米', 'value': 3},
                {'name': '苹果', 'value': 2},
                {'name': '葡萄', 'value': 2},
            ] if use_demo_fallback else []
        ),
        'risk_distribution': risk_bar,
        'confidence_risk_scatter': scatter[:50] if scatter else (
            [
                {'name': '演示', 'risk': 52, 'confidence': 89, 'severity': '一般'},
                {'name': '演示', 'risk': 82, 'confidence': 91, 'severity': '严重'},
                {'name': '演示', 'risk': 12, 'confidence': 94, 'severity': '健康'},
            ] if use_demo_fallback else []
        ),
        'diagnosis_activity': activity,
        'urgency_pie': urgency_pie,
        'filters': {
            'days': days,
            'source': source_filter,
        },
        'summary': {
            'avg_risk': avg_risk,
            'avg_confidence': avg_conf,
            'high_risk_count': risk_buckets.get('70–100% 高风险', 0),
        },
    }


def build_trend_chart_series(
    reports_dir: str,
    days: Optional[int] = None,
    source_filter: str = 'all',
    max_points: int = 7,
    label_fn: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    """
    与 visualization 相同筛选条件，取最近 max_points 条报告生成趋势折线数据。
    label_fn: 可选，接收 (generated_at, index) 返回横轴标签。
    """
    objs = _load_report_objects(
        reports_dir,
        limit=max_points,
        days=days,
        source_filter=source_filter,
    )
    if not objs:
        return None

    labels: List[str] = []
    risk: List[int] = []
    suggestion: List[int] = []
    confidence: List[int] = []

    for i, obj in enumerate(objs):
        meta = _meta(obj)
        gen = obj.get('generated_at') or ''
        if label_fn:
            labels.append(str(label_fn(gen, i)))
        else:
            labels.append(gen[:8] if len(gen) >= 8 else f'诊断{i + 1}')
        drv = _risk_percent(meta)
        risk.append(drv)
        suggestion.append(max(0, min(100, 60 + (50 - drv))))
        confidence.append(_confidence_percent(meta))

    return {
        'labels': labels,
        'risk': risk,
        'suggestion': suggestion,
        'confidence': confidence,
    }


def catalog_crop_histogram() -> Dict[str, int]:
    """从 DISEASE_DETAILS 统计知识库作物分布。"""
    try:
        from scripts.utils import DISEASE_DETAILS
    except Exception:
        return {}
    counts: Counter = Counter()
    for info in DISEASE_DETAILS.values():
        c = (info.get('crop') or '其他').strip() or '其他'
        counts[c] += 1
    return dict(counts)