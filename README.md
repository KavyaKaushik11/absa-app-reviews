# Absa app reviews

Collects public reviews of the Absa Uganda app from the Apple App Store and Google Play (Uganda) every hour, for a Power BI dashboard.

- `collect_reviews.py` – gets the newest reviews, adds them to `data/reviews.csv` and calculates the dashboard columns. Reviewer names are not saved.
- `collect_reviews.ipynb` – notebook for exploring the data. It uses the functions in `collect_reviews.py`.
- `tools/make_pbip.py` – generates the Power BI project in `powerbi/`. Run: `python tools/make_pbip.py powerbi tools/assets/CY24SU06.json`
- `.github/workflows/collect.yml` – runs the script every hour on GitHub Actions and commits the updated CSV.

## Open the dashboard (Windows)

1. Install **Power BI Desktop** from the Microsoft Store (free).
2. Download this repo: **Code → Download ZIP**, then unzip it.
3. Open `powerbi/AbsaReviews.pbip` in Power BI Desktop.
4. Select **Refresh**. If Power BI asks how to connect to the web link, choose **Anonymous**, then **Connect**.
5. Optional: **File → Save as** a `.pbix` file. This gives one file that you can copy to another PC.

Click **Refresh** at any time to get the newest reviews.

If Power BI Desktop says the file uses preview features, go to **File → Options and settings → Options → Preview features**, turn on the Power BI Project (.pbip), TMDL and PBIR options, restart Power BI Desktop and open the file again.

The dashboard has 3 pages:
- **Overview** – store, date and app version filters; review count, average rating, % positive, % neutral, % negative, rating per month, star split, reviews by sentiment, and a reviews list. Click a bar (for example "Negative") to filter the list; click it again to clear.
- **App versions** – average rating and sentiment per app version.
- **Latest reviews** – every review, newest first, with filters.

Times are shown in Uganda time (EAT, UTC+3).

## Where the logic lives

- **Python (`collect_reviews.py`)** – everything that has one value per review: Uganda time, platform name, month, short version, stars, VADER sentiment, replied. Change a rule here and the dashboard picks it up on the next **Refresh**.
- **Power BI** – only the readable column names, data types, sort orders, the measures (averages and percentages, which must recalculate when you filter) and the charts.

## CSV columns

| Column | Meaning |
|---|---|
| `store` | `apple` or `google` |
| `review_id` | The store's ID for the review |
| `rating` | Stars, 1–5 |
| `title` | Review title (Apple only) |
| `text` | Review text |
| `app_version` | App version the reviewer used (can be empty) |
| `review_date` | When the review was written (UTC) |
| `thumbs_up` | How many people marked it helpful |
| `reply_text` | Absa's reply (Google only) |
| `reply_date` | When Absa replied (UTC) |
| `fetched_at` | When this project first collected the review (UTC) |
| `platform` | `iOS` or `Android` |
| `review_date_local` | Review date in Uganda time |
| `review_day` | Review date, without the time (Uganda time) |
| `month` | First day of the review's month |
| `version` | Short version, e.g. `8.7`; `Unknown` if empty |
| `version_sort` | Number for sorting versions, e.g. `8.7` → `8007` |
| `stars` | Label such as `4 star` |
| `sentiment` | From VADER `vader_compound`: ≥ 0.05 Positive, ≤ -0.05 Negative, otherwise Neutral |
| `replied` | `Yes` / `No` for Android; `No data` for iOS |
| `hours_to_reply` | Hours between the review and Absa's reply |
| `vader_neg`, `vader_neu`, `vader_pos` | VADER: share of negative, neutral and positive wording (0–1) |
| `vader_compound` | VADER overall score, -1 (very negative) to +1 (very positive) |

The first 11 columns are the raw store data. The others are calculated from them.

## Sentiment

Sentiment comes from [VADER](https://github.com/cjhutto/vaderSentiment), not from the star rating. VADER scores the raw text (iOS: title + text; Android: text) without cleaning, because it uses words like "not", capital letters, "!" and emojis. It is a word list with rules, so it runs in the hourly job with no extra download.

Limits: English only (other languages score Neutral), very short reviews are often Neutral, and it can miss complaints that use positive words ("blank screen after successfully logging in").

## Data link for Power BI

```
https://raw.githubusercontent.com/KavyaKaushik11/absa-app-reviews/main/data/reviews.csv
```

In Power BI Desktop: **Get data → Web**, paste the link, then **Refresh** to get the latest reviews.

## Sources

- Apple: public RSS feed, newest ~500 reviews.
- Google Play: [google-play-scraper](https://pypi.org/project/google-play-scraper/). Not an official API; it can break when Google changes its site.
