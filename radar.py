import html
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
import requests


SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
JST = timezone(timedelta(hours=9))
LOOKBACK_HOURS = 36
TOP_PER_CATEGORY = 4


FEEDS = {
    "🤖 AI": [
        {
            "name": "OpenAI",
            "url": "https://openai.com/news/rss.xml",
            "authority": 5,
        },
        {
            "name": "Anthropic",
            "url": "https://www.anthropic.com/news/rss.xml",
            "authority": 5,
        },
        {
            "name": "Microsoft AI",
            "url": "https://blogs.microsoft.com/ai/feed/",
            "authority": 4,
        },
        {
            "name": "Hugging Face",
            "url": "https://huggingface.co/blog/feed.xml",
            "authority": 4,
        },
        {
            "name": "TechCrunch AI",
            "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
            "authority": 3,
        },
    ],
    "🥽 VR / XR": [
        {
            "name": "Road to VR",
            "url": "https://www.roadtovr.com/feed/",
            "authority": 4,
        },
        {
            "name": "UploadVR",
            "url": "https://www.uploadvr.com/rss/",
            "authority": 4,
        },
    ],
    "🚀 STARTUP": [
        {
            "name": "TechCrunch Startups",
            "url": "https://techcrunch.com/category/startups/feed/",
            "authority": 4,
        },
        {
            "name": "Hacker News",
            "url": "https://hnrss.org/frontpage",
            "authority": 3,
        },
        {
            "name": "Product Hunt",
            "url": "https://www.producthunt.com/feed",
            "authority": 3,
        },
    ],
}


KEYWORDS = {
    "🤖 AI": {
        "openai": 6,
        "anthropic": 6,
        "deepmind": 6,
        "agent": 5,
        "agents": 5,
        "llm": 4,
        "multimodal": 4,
        "reasoning": 4,
        "coding": 4,
        "developer": 2,
        "robotics": 3,
        "robot": 2,
        "model": 2,
        "inference": 3,
        "ai": 1,
    },
    "🥽 VR / XR": {
        "vision pro": 6,
        "quest": 6,
        "spatial computing": 6,
        "smart glasses": 6,
        "mixed reality": 5,
        "virtual reality": 5,
        "augmented reality": 5,
        "headset": 4,
        "xr": 4,
        "vr": 4,
        "ar": 4,
        "meta": 3,
        "visionos": 4,
        "android xr": 5,
        "unity": 2,
        "unreal": 2,
    },
    "🚀 STARTUP": {
        "startup": 5,
        "founder": 4,
        "funding": 5,
        "fundraise": 5,
        "raises": 4,
        "seed": 4,
        "series a": 5,
        "series b": 5,
        "venture": 3,
        "launch": 3,
        "acquisition": 4,
        "yc": 5,
        "y combinator": 5,
        "valuation": 4,
        "revenue": 3,
    },
}


def normalize_text(text):
    text = html.unescape(text or "").lower()
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def extract_summary(raw_text, max_length=180):
    text = html.unescape(raw_text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = " ".join(text.split())

    if not text:
        return ""

    if len(text) <= max_length:
        return text

    shortened = text[:max_length].rstrip(" ,.;:-")
    return shortened + "…"


def get_published_time(entry):
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        value = getattr(entry, attr, None)
        if value:
            return datetime(*value[:6], tzinfo=timezone.utc)

    return datetime.now(timezone.utc)


def get_entry_url(entry):
    link = (entry.get("link") or "").strip()
    if link:
        return link

    entry_id = (entry.get("id") or entry.get("guid") or "").strip()
    if entry_id.startswith("http://") or entry_id.startswith("https://"):
        return entry_id

    return ""


def contains_keyword(text, keyword):
    normalized_text = normalize_text(text)
    normalized_keyword = normalize_text(keyword)

    if not normalized_keyword:
        return False

    return f" {normalized_keyword} " in f" {normalized_text} "


def score_article(title, summary, category, authority=0, published=None):
    haystack = f"{title} {summary}"
    score = authority

    for keyword, weight in KEYWORDS.get(category, {}).items():
        if contains_keyword(haystack, keyword):
            score += weight

    if published:
        age_hours = max(
            0,
            (datetime.now(timezone.utc) - published).total_seconds() / 3600,
        )
        if age_hours <= 8:
            score += 3
        elif age_hours <= 18:
            score += 2
        elif age_hours <= 30:
            score += 1

    return score


def dedupe_articles(articles):
    unique = []
    seen_titles = set()
    seen_urls = set()

    for article in sorted(
        articles,
        key=lambda item: (
            item.get("score", 0),
            item.get("published", datetime.min.replace(tzinfo=timezone.utc)),
        ),
        reverse=True,
    ):
        title_key = normalize_text(article.get("title", ""))
        url = article.get("url", "")
        parsed = urlparse(url)
        url_key = f"{parsed.netloc}{parsed.path}".rstrip("/")

        if title_key in seen_titles or (url_key and url_key in seen_urls):
            continue

        seen_titles.add(title_key)
        if url_key:
            seen_urls.add(url_key)
        unique.append(article)

    return unique


def select_diverse_articles(articles, limit=TOP_PER_CATEGORY):
    ranked = sorted(
        articles,
        key=lambda item: (
            item.get("score", 0),
            item.get("published", datetime.min.replace(tzinfo=timezone.utc)),
        ),
        reverse=True,
    )

    selected = []
    selected_ids = set()
    used_sources = set()

    for article in ranked:
        source = article.get("source", "")
        if source in used_sources:
            continue

        selected.append(article)
        selected_ids.add(id(article))
        used_sources.add(source)

        if len(selected) >= limit:
            return selected

    for article in ranked:
        if id(article) in selected_ids:
            continue

        selected.append(article)
        if len(selected) >= limit:
            break

    return selected


def collect_articles(category, feeds):
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

    for feed_info in feeds:
        try:
            feed = feedparser.parse(feed_info["url"])
        except Exception as exc:
            print(f"WARN: failed to parse {feed_info['name']}: {exc}")
            continue

        if getattr(feed, "bozo", False) and not feed.entries:
            print(f"WARN: feed unavailable: {feed_info['name']}")
            continue

        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            link = get_entry_url(entry)
            raw_summary = entry.get("summary") or entry.get("description") or ""
            summary = extract_summary(raw_summary)

            if not title or not link:
                continue

            published = get_published_time(entry)
            if published < cutoff:
                continue

            score = score_article(
                title,
                summary,
                category,
                authority=feed_info.get("authority", 0),
                published=published,
            )

            articles.append(
                {
                    "title": title,
                    "url": link,
                    "source": feed_info["name"],
                    "published": published,
                    "score": score,
                    "summary": summary,
                }
            )

    unique_articles = dedupe_articles(articles)
    return select_diverse_articles(unique_articles, TOP_PER_CATEGORY)


def score_label(score):
    if score >= 16:
        return "🔥 MUST READ"
    if score >= 11:
        return "⭐ 注目"
    return "📰 Pick"


def build_message():
    today = datetime.now(JST)
    lines = [
        "☀️ *TECH RADAR*",
        today.strftime("%Y.%m.%d"),
        "",
        "AI・VR/XR・Startup の注目ニュースを無料の公開フィードから自動収集しました。",
    ]

    total = 0

    for category, feeds in FEEDS.items():
        lines.extend(
            ["", "━━━━━━━━━━━━━━━━━━", f"*{category}*", "━━━━━━━━━━━━━━━━━━", ""]
        )
        articles = collect_articles(category, feeds)

        if not articles:
            lines.append(f"過去{LOOKBACK_HOURS}時間に取得できる記事がありませんでした。")
            continue

        for index, article in enumerate(articles, 1):
            published_jst = article["published"].astimezone(JST)
            lines.append(f"*{index}. {article['title']}*")
            lines.append(
                f"{score_label(article['score'])}  ・  {article['source']}  ・  "
                f"{published_jst.strftime('%m/%d %H:%M')}"
            )

            if article["summary"]:
                lines.append(f"> {article['summary']}")

            lines.append(f"🔗 <{article['url']}|元記事を読む>")
            lines.append("")
            total += 1

    lines.extend(
        [
            "━━━━━━━━━━━━━━━━━━",
            f"📡 *{total} articles picked*  |  AI API不使用・元記事URL付き",
        ]
    )

    return "\n".join(lines)


def send_to_slack(message):
    if not SLACK_WEBHOOK_URL:
        raise RuntimeError("SLACK_WEBHOOK_URL is not configured")

    response = requests.post(
        SLACK_WEBHOOK_URL,
        json={"text": message},
        timeout=30,
    )
    response.raise_for_status()


if __name__ == "__main__":
    message = build_message()
    print(message)
    send_to_slack(message)
    print("Slack post completed.")
