# Absa app reviews

Collects public reviews of the Absa Banking app from the Apple App Store and Google Play (South Africa) every hour, for a Power BI dashboard.

- `collect_reviews.py` – gets the newest reviews and adds them to `data/reviews.csv`. Reviewer names are not saved.
- `collect_reviews.ipynb` – the same steps as a notebook, for exploring the data.
- `.github/workflows/collect.yml` – runs the script every hour on GitHub Actions and commits the updated CSV.

## Data link for Power BI

```
https://raw.githubusercontent.com/KavyaKaushik11/absa-app-reviews/main/data/reviews.csv
```

In Power BI Desktop: **Get data → Web**, paste the link, then **Refresh** to get the latest reviews.

## Sources

- Apple: public RSS feed, newest ~500 reviews.
- Google Play: [google-play-scraper](https://pypi.org/project/google-play-scraper/). Not an official API; it can break when Google changes its site.
