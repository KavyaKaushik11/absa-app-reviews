# Absa app reviews

Collects public reviews of the Absa Banking app from the Apple App Store and Google Play (South Africa) every hour, for a Power BI dashboard.

- `collect_reviews.py` – gets the newest reviews and adds them to `data/reviews.csv`. Reviewer names are not saved.
- `collect_reviews.ipynb` – the same steps as a notebook, for exploring the data.
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
- **Overview** – review count, average rating, % negative, Android reply rate, rating per week, star split.
- **App versions** – average rating and sentiment per app version.
- **Latest reviews** – every review, newest first, with filters.

Times are shown in South African time.

## Data link for Power BI

```
https://raw.githubusercontent.com/KavyaKaushik11/absa-app-reviews/main/data/reviews.csv
```

In Power BI Desktop: **Get data → Web**, paste the link, then **Refresh** to get the latest reviews.

## Sources

- Apple: public RSS feed, newest ~500 reviews.
- Google Play: [google-play-scraper](https://pypi.org/project/google-play-scraper/). Not an official API; it can break when Google changes its site.
