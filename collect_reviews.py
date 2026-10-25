"""Collect Absa Banking app reviews from the Apple App Store and Google Play (South Africa).

Adds new reviews to data/reviews.csv and removes duplicates. Safe to run as often as needed.
Reviewer names are not saved, because the CSV is published in a public repo.
"""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from google_play_scraper import Sort, reviews

APPLE_APP_ID = "1085620596"                  # Absa Banking (App Store)
GOOGLE_APP_ID = "com.barclays.absa.banking"   # Absa Banking App (Google Play)
COUNTRY = "za"
GOOGLE_MAX_REVIEWS = 1000                     # newest N reviews per run

DATA_FILE = Path(__file__).parent / "data" / "reviews.csv"

COLUMNS = ["store", "review_id", "rating", "title", "text", "app_version",
           "review_date", "thumbs_up", "reply_text", "reply_date", "fetched_at"]


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
    all_df.to_csv(DATA_FILE, index=False)
    print(f"Saved {len(all_df)} reviews to {DATA_FILE} ({len(all_df) - len(old_df)} new)")


if __name__ == "__main__":
    main()
