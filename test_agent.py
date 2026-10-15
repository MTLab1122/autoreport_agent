"""Automated test suite for the AI & Tech Intelligence Briefing Agent."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from config import AgentConfig
from sources import format_raw_intelligence_text
from synthesizer import clean_json_response, _validate_brief_structure, fallback_offline_synthesis
from pdf_generator import safe_xml, build_brief_pdf
from emailer import compose_email_payload


class TestAgentSuite(unittest.TestCase):

    def test_config_initialization(self):
        cfg = AgentConfig()
        self.assertTrue(cfg.recipient_email.endswith("@gmail.com"))
        self.assertEqual(cfg.schedule_time, "07:00")
        self.assertTrue(cfg.reports_dir.exists())
        self.assertTrue(cfg.logs_dir.exists())

    def test_safe_xml_escaping(self):
        self.assertEqual(safe_xml("Tom & Jerry"), "Tom &amp; Jerry")
        self.assertEqual(safe_xml("5 < 10 & 10 > 5"), "5 &lt; 10 &amp; 10 &gt; 5")
        self.assertEqual(safe_xml(None), "")
        self.assertEqual(safe_xml("Simple text"), "Simple text")

    def test_clean_json_response(self):
        # 1. Clean JSON
        valid = '{"key": "value"}'
        self.assertEqual(clean_json_response(valid), {"key": "value"})

        # 2. Markdown fenced JSON
        fenced = '```json\n{"date": "2026-10-15"}\n```'
        self.assertEqual(clean_json_response(fenced), {"date": "2026-10-15"})

        # 3. Preamble with JSON
        messy = 'Here is your brief:\n```json\n{"top_headline": "Breakthrough"}\n```\nHope you like it!'
        self.assertEqual(clean_json_response(messy), {"top_headline": "Breakthrough"})

    def test_validate_brief_structure(self):
        data = {"date": "2026-10-15"}
        validated = _validate_brief_structure(data, "2026-10-15")
        for pillar in ["pillar_1", "pillar_2", "pillar_3", "pillar_4", "pillar_5"]:
            self.assertIn(pillar, validated)
            self.assertIsInstance(validated[pillar], list)
        self.assertIn("top_headline", validated)
        self.assertIn("highlights", validated)

    def test_fallback_offline_synthesis(self):
        mock_raw = {
            "hacker_news": [
                {"title": "OpenAI & Anthropic Release New Models <v2>", "points": 150, "comments": 45, "url": "https://example.com"}
            ],
            "hugging_face_papers": [
                {"title": "Scaling Laws in 2026", "upvotes": 85, "summary": "Breakthrough study", "url": "https://hf.co/paper1"}
            ],
            "github_trending": [
                {"name": "cool-lab/ai-agent", "description": "Autonomous framework", "stars": 1200, "url": "https://github.com/cool-lab/ai-agent", "language": "Python"}
            ]
        }
        res = fallback_offline_synthesis(mock_raw, "2026-10-15")
        self.assertEqual(res["date"], "2026-10-15")
        self.assertTrue(len(res["highlights"]) > 0)
        self.assertTrue(len(res["pillar_1"]) > 0)
        self.assertTrue(len(res["pillar_5"]) > 0)

    def test_format_raw_intelligence_text(self):
        mock_raw = {
            "timestamp": "2026-10-15T00:00:00Z",
            "hacker_news": [{"title": "HN Post", "points": 10, "url": "https://hn.com"}],
            "hugging_face_papers": [{"title": "Paper", "upvotes": 20, "summary": "Text", "url": "https://hf.co"}],
            "github_trending": [{"name": "repo/test", "stars": 50, "description": "Desc", "url": "https://gh.com"}],
        }
        text = format_raw_intelligence_text(mock_raw)
        self.assertIn("LIVE AGGREGATED SIGNALS", text)
        self.assertIn("HN Post", text)
        self.assertIn("Paper", text)
        self.assertIn("repo/test", text)

    def test_pdf_generation_with_special_characters(self):
        report_data = {
            "date": "2026-10-15",
            "top_headline": "NVIDIA & Apple Announce <Next-Gen> AI Silicon",
            "highlights": [
                "NVIDIA & AMD report record GPU shipments.",
                "Anthropic updates Claude 3.5 Sonnet <100k context>.",
                "Research paper: 5 > 4 & scalable benchmarks."
            ],
            "pillar_1": [
                {
                    "name": "Model-X & Y",
                    "creator": "Lab <Alpha>",
                    "summary": "State-of-the-art benchmark with 10 > 5 performance gain.",
                    "source_url": "https://example.com?query=a&b=c",
                }
            ],
            "pillar_2": [],
            "pillar_3": [],
            "pillar_4": [],
            "pillar_5": [],
        }
        with TemporaryDirectory() as tmpdir:
            pdf_out = Path(tmpdir) / "test_output.pdf"
            built_path = build_brief_pdf(report_data, pdf_out)
            self.assertTrue(built_path.exists())
            self.assertGreater(built_path.stat().st_size, 1000)

    def test_email_payload_construction(self):
        report_data = {
            "date": "2026-10-15",
            "top_headline": "Frontier Breakthrough",
            "highlights": ["H1", "H2", "H3"],
        }
        with TemporaryDirectory() as tmpdir:
            dummy_pdf = Path(tmpdir) / "dummy.pdf"
            dummy_pdf.write_bytes(b"%PDF-1.4 dummy content")

            payload = compose_email_payload(report_data, dummy_pdf, recipient_email="muhammadtalhapro1@gmail.com")
            self.assertEqual(payload["to"], ["muhammadtalhapro1@gmail.com"])
            self.assertIn("Frontier Breakthrough", payload["subject"])
            self.assertIn("H1", payload["html"])
            self.assertEqual(len(payload["attachments"]), 1)
            self.assertEqual(payload["attachments"][0]["filename"], "dummy.pdf")


if __name__ == "__main__":
    unittest.main()
