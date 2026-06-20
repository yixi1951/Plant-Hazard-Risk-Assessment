"""dashboard_analytics 聚合逻辑单元测试。"""

import json
import os
import tempfile
import unittest

from scripts.dashboard_analytics import (
    build_batch_visualization,
    build_trend_chart_series,
    build_visualization_payload,
    catalog_crop_histogram,
)


class TestDashboardAnalytics(unittest.TestCase):
    def test_catalog_crop_histogram_nonempty(self):
        hist = catalog_crop_histogram()
        self.assertIsInstance(hist, dict)
        self.assertGreater(len(hist), 0)

    def test_build_visualization_from_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta = {
                'disease_name': '玉米大斑病',
                'severity': '严重',
                'disease_risk_percent': 82,
                'severity_confidence': 0.91,
                'crop': '玉米',
                'urgency': '高',
            }
            path = os.path.join(tmp, 'r1.json')
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump({'generated_at': '20250610T120000Z', 'meta': meta}, fh)
            viz = build_visualization_payload(tmp, catalog_crop_counts={'玉米': 5})
            self.assertEqual(viz['report_count'], 1)
            self.assertEqual(viz['summary']['avg_risk'], 82.0)
            self.assertEqual(len(viz['severity_pie']), 3)
            self.assertTrue(viz['disease_top'])

    def test_fallback_when_no_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            viz = build_visualization_payload(tmp, catalog_crop_counts={'苹果': 3})
            self.assertEqual(viz['report_count'], 0)
            self.assertTrue(viz['crop_distribution'])

    def test_source_filter_demo_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'real.json'), 'w', encoding='utf-8') as fh:
                json.dump({
                    'generated_at': '20250612T120000Z',
                    'demo': False,
                    'meta': {'disease_risk_percent': 50, 'disease_name': 'A'},
                }, fh)
            with open(os.path.join(tmp, 'demo_demo_x.json'), 'w', encoding='utf-8') as fh:
                json.dump({
                    'generated_at': '20250611T120000Z',
                    'demo': True,
                    'meta': {'disease_risk_percent': 20, 'disease_name': 'B'},
                }, fh)
            real_only = build_visualization_payload(tmp, source_filter='real')
            self.assertEqual(real_only['report_count'], 1)
            demo_only = build_visualization_payload(tmp, source_filter='demo')
            self.assertEqual(demo_only['report_count'], 1)

    def test_build_batch_visualization(self):
        results = [
            {'disease_name': '玉米大斑病', 'severity': '严重', 'risk_score': 80},
            {'filename': 'bad.jpg', 'error': 'fail'},
        ]
        bv = build_batch_visualization(results)
        self.assertEqual(bv['success_count'], 1)
        self.assertEqual(bv['fail_count'], 1)
        self.assertEqual(bv['outcome_pie'][0]['value'], 1)

    def test_trend_follows_source_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'real.json'), 'w', encoding='utf-8') as fh:
                json.dump({
                    'generated_at': '20250612T120000Z',
                    'demo': False,
                    'meta': {'disease_risk_percent': 50, 'severity_confidence': 0.9},
                }, fh)
            with open(os.path.join(tmp, 'demo_demo_x.json'), 'w', encoding='utf-8') as fh:
                json.dump({
                    'generated_at': '20250611T120000Z',
                    'demo': True,
                    'meta': {'disease_risk_percent': 20, 'severity_confidence': 0.95},
                }, fh)
            trend_real = build_trend_chart_series(tmp, source_filter='real', max_points=7)
            self.assertIsNotNone(trend_real)
            self.assertEqual(len(trend_real['risk']), 1)
            self.assertEqual(trend_real['risk'][0], 50)
            trend_demo = build_trend_chart_series(tmp, source_filter='demo', max_points=7)
            self.assertEqual(trend_demo['risk'][0], 20)


if __name__ == '__main__':
    unittest.main()