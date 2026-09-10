import unittest

from radar import (
    dedupe_articles,
    extract_summary,
    normalize_text,
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

        self.assertEqual([article["source"] for article in selected], [
            "Source A",
            "Source B",
            "Source C",
            "Source D",
        ])
        self.assertNotIn("A2", [article["title"] for article in selected])

    def test_select_diverse_articles_fills_remaining_slots_by_score(self):
        articles = [
            {"title": "A1", "source": "Source A", "score": 20},
            {"title": "A2", "source": "Source A", "score": 18},
            {"title": "B1", "source": "Source B", "score": 19},
            {"title": "B2", "source": "Source B", "score": 17},
        ]

        selected = select_diverse_articles(articles, limit=4)

        self.assertEqual([article["title"] for article in selected], [
            "A1",
            "B1",
            "A2",
            "B2",
        ])


if __name__ == "__main__":
    unittest.main()
