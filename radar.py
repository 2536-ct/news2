import os
from datetime import datetime, timedelta, timezone

import feedparser
import requests


SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]

JST = timezone(timedelta(hours=9))


FEEDS = {
    "🤖 AI": [
        {
            "name": "TechCrunch AI",
            "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        },
    ],

    "🥽 VR / XR": [
        {
            "name": "Road to VR",
            "url": "https://www.roadtovr.com/feed/",
        },
    ],

    "🚀 STARTUP": [
        {
            "name": "TechCrunch Startups",
            "url": "https://techcrunch.com/category/startups/feed/",
        },
    ],
}


KEYWORDS = {
    "🤖 AI": [
        "openai",
        "anthropic",
        "google",
        "deepmind",
        "agent",
        "agents",
        "model",
        "llm",
        "multimodal",
        "robot",
        "robotics",
        "coding",
        "developer",
    ],

    "🥽 VR / XR": [
        "vr",
        "xr",
        "ar",
        "quest",
        "vision pro",
        "spatial",
        "headset",
        "glasses",
        "meta",
        "virtual reality",
        "augmented reality",
        "mixed reality",
    ],

    "🚀 STARTUP": [
        "startup",
        "founder",
        "funding",
        "fundraise",
        "raises",
        "seed",
        "series a",
        "series b",
        "venture",
        "launch",
        "acquisition",
        "yc",
    ],
}


def get_published_time(entry):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt

    return datetime.now(timezone.utc)


def score_article(title, category):
    title_lower = title.lower()

    score = 0

    for keyword in KEYWORDS.get(category, []):
        if keyword.lower() in title_lower:
            score += 1

    return score


def collect_articles(category, feeds):
    articles = []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=30)

    for feed_info in feeds:
        feed = feedparser.parse(feed_info["url"])

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                continue

            published = get_published_time(entry)

            if published < cutoff:
                continue

            score = score_article(title, category)

            articles.append(
                {
                    "title": title,
                    "url": link,
                    "source": feed_info["name"],
                    "published": published,
                    "score": score,
                }
            )

    articles.sort(
        key=lambda x: (
            x["score"],
            x["published"],
        ),
        reverse=True,
    )

    unique = []
    seen = set()

    for article in articles:
        key = article["title"].lower()

        if key in seen:
            continue

        seen.add(key)
        unique.append(article)

    return unique[:3]


def build_message():
    today = datetime.now(JST)

    lines = []

    lines.append("☀️ *TECH RADAR*")
    lines.append(today.strftime("%Y.%m.%d"))
    lines.append("")
    lines.append(
        "AI・VR/XR・Startup の注目ニュースを自動収集しました。"
    )

    total = 0

    for category, feeds in FEEDS.items():

        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append(f"*{category}*")
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append("")

        articles = collect_articles(category, feeds)

        if not articles:
            lines.append("過去30時間に新しい記事がありませんでした。")
            continue

        for index, article in enumerate(articles, 1):

            published_jst = article["published"].astimezone(JST)

            lines.append(
                f"*{index}. {article['title']}*"
            )

            lines.append(
                f"📰 {article['source']} | "
                f"{published_jst.strftime('%m/%d %H:%M')}"
            )

            lines.append(
                f"🔗 <{article['url']}|元記事を読む>"
            )

            lines.append("")

            total += 1

    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📡 {total} articles picked")

    return "\n".join(lines)


def send_to_slack(message):
    response = requests.post(
        SLACK_WEBHOOK_URL,
        json={
            "text": message
        },
        timeout=30,
    )

    response.raise_for_status()


if __name__ == "__main__":
    message = build_message()

    print(message)

    send_to_slack(message)

    print("Slack post completed.")
