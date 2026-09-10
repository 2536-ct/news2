import unittest

from radar import (
    dedupe_articles,
    extract_summary,
    normalize_text,
    score_article,
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


if __name__ == "__main__":
    unittest.main()
