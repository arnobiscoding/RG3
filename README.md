# RG3 - Wingo Data Lab

A fun learning project to collect Wingo draw data, analyze patterns with statistics, and experiment with ML models for number prediction research.

## Project Vision

This repository is focused on three steps:

1. Collect clean historical Wingo data automatically.
2. Build statistical insights and feature engineering pipelines.
3. Train and evaluate ML models to explore predictive signals.

Note: This project is for learning and experimentation. Random systems may not be reliably predictable in real-world settings.

## Current Status

- Data scraping is implemented with Selenium.
- Two data output modes are available:
  - `scraper/scraper.py`: scrapes and upserts data to MongoDB.
  - `scraper/scraper_txt.py`: scrapes and saves data as TXT in `scraper/output/`.

## Repository Structure

```text
RG3/
  requirements.txt
  README.md
  scraper/
    scraper.py
    scraper_txt.py
    output/
```

## Requirements

- Python 3.10+
- Google Chrome installed
- Internet connection
- A valid login for the target Wingo site
- MongoDB URI (only needed for `scraper.py`)

## Installation

From the repository root:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file (inside `scraper/` for current script behavior) with:

```env
PHONE_NUMBER=your_phone_number
PASSWORD=your_password
MONGO_URI=your_mongodb_connection_string
```

`MONGO_URI` is required for `scraper.py` and optional for `scraper_txt.py`.

## Run the Scrapers

From `scraper/`:

```bash
python scraper.py
```

or

```bash
python scraper_txt.py
```

## Data Fields

Each scraped record includes:

- `period`
- `number`
- `color`
- `scraped_at`

The scraper also validates sequence continuity before saving/uploading records.

## ML and Statistics Plan

Planned next steps:

1. Add dataset export utilities (CSV/Parquet).
2. Add EDA notebooks for frequency, streaks, transitions, and rolling-window behavior.
3. Build baseline models:
   - Markov transition baseline
   - Logistic regression / tree-based classifiers
   - Sequence models for short-term context
4. Add evaluation framework with walk-forward validation.
5. Track experiments and compare model performance over time.

## Safety and Responsible Use

- Do not commit credentials or sensitive `.env` files.
- Use this project responsibly and in line with local laws and platform terms.
- Treat outputs as educational signals, not guaranteed outcomes.

## Contributing

Improvements are welcome:

- Better selectors and scraper robustness
- Data cleaning and feature engineering
- Stronger validation and backtesting pipelines
- Model comparison and reporting

---

Built as a learning playground for data engineering, statistics, and machine learning on time-series style game data.
