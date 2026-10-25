"""Collect Absa Uganda app reviews from the Apple App Store and Google Play (Uganda).

Adds new reviews to data/reviews.csv and removes duplicates. Safe to run as often as needed.
Reviewer names are not saved, because the CSV is published in a public repo.
"""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from google_play_scraper import Sort, reviews
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

APPLE_APP_ID = "1485713913"                      # Absa Uganda (App Store)
GOOGLE_APP_ID = "com.absa.ug.mobile.android.ui"   # Absa Uganda (Google Play)
COUNTRY = "ug"
GOOGLE_MAX_REVIEWS = 1000                     # newest N reviews per run

DATA_FILE = Path(__file__).parent / "data" / "reviews.csv"

LOCAL_TZ = "Africa/Kampala"                   # Uganda time (EAT, UTC+3)

# Raw store data. New columns go at the end, so older dashboards that read
# only the first 11 columns keep working.
COLUMNS = ["store", "review_id", "rating", "title", "text", "app_version",
           "review_date", "thumbs_up", "reply_text", "reply_date", "fetched_at"]

# Added by add_derived_columns() for the dashboard.
DERIVED_COLUMNS = ["platform", "review_date_local", "review_day", "month", "version",
                   "version_sort", "stars", "sentiment", "replied", "hours_to_reply",
                   "vader_neg", "vader_neu", "vader_pos", "vader_compound"]

# Standard VADER cut-offs on the compound score.
POSITIVE_FROM = 0.05
NEGATIVE_FROM = -0.05

_vader = SentimentIntensityAnalyzer()


def fetch_apple_reviews(app_id=APPLE_APP_ID, country=COUNTRY, max_pages=10):
    """Apple's public RSS feed: up to 10 pages of 50 reviews."""
    rows = []
    for page in range(1, max_pages + 1):
        url = (f"https://itunes.apple.com/{country}/rss/customerreviews/"
               f"page={page}/id={app_id}/sortby=mostrecent/json")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        entries = resp.json().get("feed", {}).get("entry", [])
        if isinstance(entries, dict):   # a page with one entry is not a list
            entries = [entries]
        entries = [e for e in entries if "im:rating" in e]
        if not entries:
            break
        for e in entries:
            rows.append({
                "store": "apple",
                "review_id": e["id"]["label"],
                "rating": int(e["im:rating"]["label"]),
                "title": e["title"]["label"],
                "text": e["content"]["label"],
                "app_version": e["im:version"]["label"],
                "review_date": pd.to_datetime(e["updated"]["label"], utc=True),
                "thumbs_up": int(e.get("im:voteSum", {}).get("label", 0)),
                "reply_text": None,   # not in Apple's public feed
                "reply_date": None,
            })
    return pd.DataFrame(rows)


def fetch_google_reviews(app_id=GOOGLE_APP_ID, country=COUNTRY, max_reviews=GOOGLE_MAX_REVIEWS):
    """google-play-scraper: not an official API, can break when Google changes its site."""
    results, token = [], None
    while len(results) < max_reviews:
        batch, token = reviews(app_id, lang="en", country=country, sort=Sort.NEWEST,
                               count=min(200, max_reviews - len(results)),
                               continuation_token=token)
        results.extend(batch)
        if not batch or token is None or token.token is None:
            break
    rows = [{
        "store": "google",
        "review_id": r["reviewId"],
        "rating": r["score"],
        "title": None,   # Google reviews have no title
        "text": r["content"],
        "app_version": r.get("reviewCreatedVersion") or r.get("appVersion"),
        # The scraper returns naive datetimes in the machine's local time zone.
        "review_date": pd.Timestamp(r["at"].astimezone(timezone.utc)),
        "thumbs_up": r["thumbsUpCount"],
        "reply_text": r.get("replyContent"),
        "reply_date": pd.Timestamp(r["repliedAt"].astimezone(timezone.utc)) if r.get("repliedAt") else None,
    } for r in results]
    return pd.DataFrame(rows)


def short_version(app_version):
    """'8.7.2' -> '8.7'; Android names like '26.8.1 - August-Release' -> '26.8'."""
    if pd.isna(app_version) or not str(app_version).strip():
        return "Unknown"
    parts = str(app_version).split(" - ")[0].strip().split(".")
    return ".".join(parts[:2])


def version_sort_key(version):
    """'8.7' -> 8007 and '8.10' -> 8010, so versions sort as numbers, not text."""
    try:
        major, minor = version.split(".")[:2]
        return int(major) * 1000 + int(minor)
    except ValueError:
        return 0


def text_to_score(title, text):
    """Raw text for VADER: iOS title + text, Android text only (Google has no title).

    No cleaning on purpose: VADER uses negations ("not"), capitals, "!" and emojis.
    """
    title = "" if pd.isna(title) else str(title).strip()
    text = "" if pd.isna(text) else str(text).strip()
    return f"{title}. {text}" if title and text else title or text


def sentiment(compound):
    if compound >= POSITIVE_FROM:
        return "Positive"
    if compound <= NEGATIVE_FROM:
        return "Negative"
    return "Neutral"


def add_derived_columns(df):
    """Add one-value-per-review columns for the dashboard.

    Recalculated for every row on each run, so a rule change here reaches the
    dashboard on the next Refresh. Measures (averages, percentages) stay in Power BI,
    because they must recalculate when the user filters.
    """
    df = df.copy()
    review_utc = pd.to_datetime(df["review_date"], utc=True, format="mixed")
    reply_utc = pd.to_datetime(df["reply_date"], utc=True, format="mixed")
    review_local = review_utc.dt.tz_convert(LOCAL_TZ)

    df["platform"] = df["store"].map({"apple": "iOS", "google": "Android"})
    df["review_date_local"] = review_local.dt.strftime("%Y-%m-%d %H:%M:%S")
    df["review_day"] = review_local.dt.strftime("%Y-%m-%d")
    df["month"] = review_local.dt.strftime("%Y-%m-01")
    df["version"] = df["app_version"].map(short_version)
    df["version_sort"] = df["version"].map(version_sort_key)
    df["stars"] = df["rating"].astype(int).astype(str) + " star"
    scores = pd.DataFrame([_vader.polarity_scores(text_to_score(t, x))
                           for t, x in zip(df["title"], df["text"])], index=df.index)
    for part in ["neg", "neu", "pos", "compound"]:
        df[f"vader_{part}"] = scores[part]
    df["sentiment"] = df["vader_compound"].map(sentiment)
    # Apple's public feed has no developer replies, so iOS gets "No data".
    has_reply = df["reply_text"].notna() & (df["reply_text"].astype(str).str.strip() != "")
    df["replied"] = "No"
    df.loc[has_reply, "replied"] = "Yes"
    df.loc[df["store"] == "apple", "replied"] = "No data"
    df["hours_to_reply"] = ((reply_utc - review_utc).dt.total_seconds() / 3600).round(1)
    return df[COLUMNS + DERIVED_COLUMNS]


def main():
    apple_df = fetch_apple_reviews()
    google_df = fetch_google_reviews()
    print(f"Apple: {len(apple_df)} reviews, Google: {len(google_df)} reviews")

    new_df = pd.concat([apple_df, google_df], ignore_index=True)
    new_df["fetched_at"] = datetime.now(timezone.utc).isoformat(sep=" ", timespec="seconds")
    new_df = new_df[COLUMNS].astype({"review_id": str})

    DATA_FILE.parent.mkdir(exist_ok=True)
    if DATA_FILE.exists():
        old_df = pd.read_csv(DATA_FILE, dtype={"review_id": str})
        all_df = pd.concat([old_df, new_df], ignore_index=True)
    else:
        old_df = pd.DataFrame(columns=COLUMNS)
        all_df = new_df

    # Keep the newest copy of each review, because people can edit their reviews.
    # fetched_at keeps the first time we saw the review, so unchanged rows stay identical
    # and the hourly commit only contains real changes.
    all_df["fetched_at"] = all_df.groupby(["store", "review_id"])["fetched_at"].transform("first")
    all_df = all_df.drop_duplicates(subset=["store", "review_id"], keep="last")[COLUMNS]
    all_df = add_derived_columns(all_df)
    all_df.to_csv(DATA_FILE, index=False)
    print(f"Saved {len(all_df)} reviews to {DATA_FILE} ({len(all_df) - len(old_df)} new)")


if __name__ == "__main__":
    main()
