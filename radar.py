import html
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
import requests


SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL_ID = os.environ.get("SLACK_CHANNEL_ID", "")
SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"

JST = timezone(timedelta(hours=9))
LOOKBACK_HOURS = 36
TOP_PER_CATEGORY = 4

_ARGOS_TRANSLATOR = None
_ARGOS_INIT_ATTEMPTED = False


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


def collect_digest():
    return {
        category: collect_articles(category, feeds)
        for category, feeds in FEEDS.items()
    }


def score_label(score):
    if score >= 16:
        return "🔥 MUST READ"
    if score >= 11:
        return "⭐ 注目"
    return "📰 Pick"


def get_argos_translator():
    global _ARGOS_TRANSLATOR, _ARGOS_INIT_ATTEMPTED

    if _ARGOS_INIT_ATTEMPTED:
        return _ARGOS_TRANSLATOR

    _ARGOS_INIT_ATTEMPTED = True

    try:
        import argostranslate.package
        import argostranslate.translate

        from_code = "en"
        to_code = "ja"

        installed_languages = argostranslate.translate.get_installed_languages()
        from_lang = next(
            (language for language in installed_languages if language.code == from_code),
            None,
        )
        to_lang = next(
            (language for language in installed_languages if language.code == to_code),
            None,
        )

        if from_lang is None or to_lang is None:
            print("INFO: installing Argos Translate en→ja language package")
            argostranslate.package.update_package_index()
            available_packages = argostranslate.package.get_available_packages()
            package = next(
                (
                    item
                    for item in available_packages
                    if item.from_code == from_code and item.to_code == to_code
                ),
                None,
            )

            if package is None:
                raise RuntimeError("Argos en→ja package is not available")

            argostranslate.package.install_from_path(package.download())
            installed_languages = argostranslate.translate.get_installed_languages()
            from_lang = next(
                language for language in installed_languages if language.code == from_code
            )
            to_lang = next(
                language for language in installed_languages if language.code == to_code
            )

        translation = from_lang.get_translation(to_lang)
        _ARGOS_TRANSLATOR = translation.translate
        return _ARGOS_TRANSLATOR
    except Exception as exc:
        print(f"WARN: Japanese translation unavailable: {exc}")
        _ARGOS_TRANSLATOR = None
        return None


def safe_translate(text, translator=None):
    text = (text or "").strip()
    if not text:
        return ""

    translator = translator or get_argos_translator()
    if translator is None:
        return ""

    try:
        return (translator(text) or "").strip()
    except Exception as exc:
        print(f"WARN: translation failed: {exc}")
        return ""


def build_parent_message(digest, now=None):
    now = now or datetime.now(JST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=JST)
    else:
        now = now.astimezone(JST)

    total = sum(len(articles) for articles in digest.values())
    lines = [
        "☀️ *TECH RADAR*",
        now.strftime("%Y.%m.%d"),
        "",
        "今日の AI・VR/XR・Startup ニュースをピックアップしました。",
        "",
    ]

    for category in FEEDS:
        lines.append(f"{category}  {len(digest.get(category, []))}件")

    lines.extend(
        [
            "",
            f"📡 *本日のニュース: {total}件*",
            "👇 和訳・原文・元記事URLはこの投稿のスレッドへ",
        ]
    )
    return "\n".join(lines)


def build_thread_message(category, articles, translator=None):
    lines = [f"*{category}*", ""]

    if translator is None:
        translator = get_argos_translator()

    for index, article in enumerate(articles, 1):
        title = article.get("title", "").strip()
        summary = article.get("summary", "").strip()
        japanese_title = safe_translate(title, translator)
        japanese_summary = safe_translate(summary, translator)
        published = article.get("published")

        if japanese_title:
            lines.append(f"*{index}. {japanese_title}*")
            lines.append(f"Original: {title}")
        else:
            lines.append(f"*{index}. {title}*")
            lines.append("🇯🇵 和訳を取得できませんでした")

        if japanese_summary:
            lines.append(f"> 🇯🇵 {japanese_summary}")
        elif summary:
            lines.append(f"> {summary}")

        meta = f"{score_label(article.get('score', 0))}  ・  {article.get('source', 'Unknown')}"
        if published:
            meta += f"  ・  {published.astimezone(JST).strftime('%m/%d %H:%M')}"
        lines.append(meta)
        lines.append(f"🔗 <{article.get('url', '')}|元記事を読む>")
        lines.append("")

    return "\n".join(lines).rstrip()


def build_slack_payload(text, channel_id, thread_ts=None):
    payload = {"channel": channel_id, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    return payload


def post_slack_message(text, thread_ts=None):
    if not SLACK_BOT_TOKEN:
        raise RuntimeError("SLACK_BOT_TOKEN is not configured")
    if not SLACK_CHANNEL_ID:
        raise RuntimeError("SLACK_CHANNEL_ID is not configured")

    response = requests.post(
        SLACK_POST_MESSAGE_URL,
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json=build_slack_payload(text, SLACK_CHANNEL_ID, thread_ts),
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data.get('error', 'unknown_error')}")

    return data["ts"]


def post_threaded_digest(digest):
    parent_ts = post_slack_message(build_parent_message(digest))
    translator = get_argos_translator()

    for category, articles in digest.items():
        if not articles:
            continue

        message = build_thread_message(category, articles, translator=translator)
        post_slack_message(message, thread_ts=parent_ts)
        time.sleep(1.1)

    return parent_ts


def build_message(digest=None):
    digest = digest or collect_digest()
    today = datetime.now(JST)
    lines = [
        "☀️ *TECH RADAR*",
        today.strftime("%Y.%m.%d"),
        "",
        "AI・VR/XR・Startup の注目ニュースを無料の公開フィードから自動収集しました。",
    ]

    total = 0

    for category, articles in digest.items():
        lines.extend(
            ["", "━━━━━━━━━━━━━━━━━━", f"*{category}*", "━━━━━━━━━━━━━━━━━━", ""]
        )

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


def main():
    digest = collect_digest()

    if SLACK_BOT_TOKEN and SLACK_CHANNEL_ID:
        post_threaded_digest(digest)
        print("Slack threaded post completed.")
        return

    if SLACK_WEBHOOK_URL:
        print("WARN: bot token/channel not configured; using legacy webhook fallback")
        send_to_slack(build_message(digest))
        print("Slack webhook post completed.")
        return

    raise RuntimeError(
        "Configure SLACK_BOT_TOKEN + SLACK_CHANNEL_ID for threads, "
        "or SLACK_WEBHOOK_URL for fallback posting."
    )


if __name__ == "__main__":
    main()
