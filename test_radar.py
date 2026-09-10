import unittest
from datetime import datetime, timezone

from radar import (
    build_parent_message,
    build_slack_payload,
    build_thread_message,
    dedupe_articles,
    extract_summary,
    normalize_text,
    safe_translate,
    score_article,
    select_diverse_articles,
)


class RadarV2Tests(unittest.TestCase):
    def test_normalize_text_collapses_case_punctuation_and_spacing(self):
        self.assertEqual(
            normalize_text("  OpenAI: New   Agent!  "),
            "openai new agent",
        )

    def test_score_article_uses_title_summary_and_weighted_keywords(self):
        score = score_article(
            "New developer tool launches",
            "OpenAI releases an AI agent for coding workflows.",
            "🤖 AI",
        )
        self.assertGreaterEqual(score, 10)

    def test_short_keywords_do_not_match_inside_unrelated_words(self):
        score = score_article(
            "Company raises capital for a retail expansion",
            "Traditional retail chain announces a financing round.",
            "🤖 AI",
        )
        self.assertEqual(score, 0)

    def test_extract_summary_removes_html_and_truncates_cleanly(self):
        summary = extract_summary(
            "<p>Spatial computing startup launches a new headset platform for developers.</p>",
            max_length=42,
        )
        self.assertNotIn("<p>", summary)
        self.assertLessEqual(len(summary), 43)
        self.assertTrue(summary.endswith("…"))

    def test_dedupe_articles_merges_near_identical_titles(self):
        articles = [
            {
                "title": "OpenAI launches new agent platform",
                "url": "https://example.com/a?utm_source=x",
                "score": 12,
            },
            {
                "title": "OpenAI: launches new agent platform!",
                "url": "https://example.org/b",
                "score": 8,
            },
            {
                "title": "Meta unveils new XR headset",
                "url": "https://example.com/c",
                "score": 9,
            },
        ]

        unique = dedupe_articles(articles)

        self.assertEqual(len(unique), 2)
        self.assertEqual(unique[0]["score"], 12)

    def test_select_diverse_articles_prefers_one_article_per_source_first(self):
        articles = [
            {"title": "A1", "source": "Source A", "score": 20},
            {"title": "A2", "source": "Source A", "score": 19},
            {"title": "B1", "source": "Source B", "score": 18},
            {"title": "C1", "source": "Source C", "score": 17},
            {"title": "D1", "source": "Source D", "score": 16},
        ]

        selected = select_diverse_articles(articles, limit=4)

        self.assertEqual(
            [article["source"] for article in selected],
            ["Source A", "Source B", "Source C", "Source D"],
        )
        self.assertNotIn("A2", [article["title"] for article in selected])

    def test_select_diverse_articles_fills_remaining_slots_by_score(self):
        articles = [
            {"title": "A1", "source": "Source A", "score": 20},
            {"title": "A2", "source": "Source A", "score": 18},
            {"title": "B1", "source": "Source B", "score": 19},
            {"title": "B2", "source": "Source B", "score": 17},
        ]

        selected = select_diverse_articles(articles, limit=4)

        self.assertEqual(
            [article["title"] for article in selected],
            ["A1", "B1", "A2", "B2"],
        )

    def test_safe_translate_returns_empty_string_when_translator_fails(self):
        def broken_translator(_text):
            raise RuntimeError("translation failed")

        self.assertEqual(safe_translate("Hello", broken_translator), "")
        self.assertEqual(safe_translate("", broken_translator), "")

    def test_build_parent_message_summarizes_category_counts(self):
        digest = {
            "🤖 AI": [{"title": "A"}, {"title": "B"}],
            "🥽 VR / XR": [{"title": "C"}],
            "🚀 STARTUP": [],
        }

        message = build_parent_message(
            digest,
            now=datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc),
        )

        self.assertIn("TECH RADAR", message)
        self.assertIn("🤖 AI  2件", message)
        self.assertIn("🥽 VR / XR  1件", message)
        self.assertIn("🚀 STARTUP  0件", message)
        self.assertIn("3件", message)
        self.assertIn("スレッド", message)

    def test_build_thread_message_contains_japanese_and_original_text(self):
        article = {
            "title": "OpenAI launches a new agent",
            "summary": "The tool helps developers automate coding tasks.",
            "url": "https://example.com/article",
            "source": "OpenAI",
            "score": 16,
            "published": datetime(2026, 9, 10, 0, 0, tzinfo=timezone.utc),
        }

        translations = {
            article["title"]: "OpenAIが新しいエージェントを発表",
            article["summary"]: "開発者のコーディング作業を自動化するツールです。",
        }

        message = build_thread_message(
            "🤖 AI",
            [article],
            translator=lambda text: translations[text],
        )

        self.assertIn("OpenAIが新しいエージェントを発表", message)
        self.assertIn("Original: OpenAI launches a new agent", message)
        self.assertIn("開発者のコーディング作業", message)
        self.assertIn("https://example.com/article", message)

    def test_build_slack_payload_adds_thread_ts_only_for_reply(self):
        parent = build_slack_payload("hello", "C123")
        reply = build_slack_payload("details", "C123", thread_ts="123.456")

        self.assertEqual(parent, {"channel": "C123", "text": "hello"})
        self.assertEqual(
            reply,
            {"channel": "C123", "text": "details", "thread_ts": "123.456"},
        )


if __name__ == "__main__":
    unittest.main()
