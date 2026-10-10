[README (1)(1).md](https://github.com/user-attachments/files/33279521/README.1.1.md)
# 🏭 Manufacturer Scraper

A Flask web app that scrapes Google Maps for manufacturer/business listings across India's major industrial belts, and cross-references every result against a master Excel database to separate **new** companies from **already-known (common)** ones.

## Features

- **Wide coverage** — searches 18 states and 235 industrial cities/clusters (e.g. Sriperumbudur, Manesar, Chakan, Sanand) for any category you type in.
- **New vs. common detection** — every scraped listing is matched against your `master_database.xlsx` by phone number:
  - **New companies** are written to a fresh Excel file and appended to the master database (`Sheet2`).
  - **Common companies** (already in the master) get a rebuilt history row combining every category, address, city, and state ever recorded for that phone number, plus anything new found this run.
- **Parallel scraping** — up to 5 states scraped concurrently via a thread pool, each with its own Chrome/Selenium driver.
- **Live progress UI** — a single-page dashboard shows a progress bar, running counts of new/common companies, cities completed, and a live scrolling log.
- **Download results** — one-click download buttons for both the new-companies file and the common-companies file once a run finishes.
- **Detailed timing breakdown** — after each run, a full stage-by-stage timing report (page load, scrolling, per-listing extraction, master load/write, etc.) is logged for performance tuning.
- **Resilient scraping** — automatically restarts the Chrome driver on a crash and retries the current city before giving up.

## Tech Stack

- **Backend:** Flask, Selenium (Chrome via Selenium Manager), pandas, openpyxl
- **Frontend:** Single-page HTML/CSS/JS (`templates/index.html`), no framework — polls `/progress` every 3 seconds
- **Storage:** Excel (`.xlsx`) master database, indexed in memory by normalized phone number

## Project Structure

```
.
├── app.py                  # Flask app, scraper logic, and orchestration
├── templates/
│   └── index.html          # Single-page dashboard UI
├── master_database.xlsx    # Your permanent company list (not included — see below)
└── requirements.txt
```

## Requirements

- Python 3.9+
- Google Chrome installed (Selenium Manager resolves the matching driver automatically)
- Python packages:
  ```
  flask
  selenium
  pandas
  openpyxl
  ```

## Setup

1. Clone the repo and install dependencies:
   ```bash
   pip install flask selenium pandas openpyxl
   ```
2. Make sure Google Chrome is installed on the machine running the scraper.
3. Place your master database as `master_database.xlsx` in the project root (or point to a different file from the UI). It should contain a `Phone Number` column, plus `Company Name`, `Address`, `City`, `State`, and `Category` where available. If the file doesn't exist yet, the app will start with an empty master list.
4. Run the app:
   ```bash
   python app.py
   ```
5. Open `http://localhost:5000` in your browser.

## Usage

1. Enter a category to search (e.g. `PCB manufacturers`, `sensors`, `industrial automation`) — or pick one of the suggestion chips.
2. Optionally change the master file path (defaults to `master_database.xlsx`).
3. Click **Start Scraping**. The app will work through all 235 cities across 18 states, 5 at a time.
4. Watch live progress: cities completed, new companies found, common companies found, and a scrolling log.
5. When the run finishes, download:
   - **New Companies** — an Excel file of everything not previously in your master database (also auto-appended to `Sheet2` of the master file).
   - **Common Companies** — an Excel file of already-known companies, with their full multi-category/address/city/state history.

## Output Columns

**New companies file:** `Company Name`, `Phone Number`, `Address`, `Website`, `City`, `State`, `Category`

**Common companies file:** `Company Name`, `Phone Number`, `Website`, plus numbered `Address 1..N`, `City 1..N`, `State 1..N`, `Category 1..N` columns covering every historical + newly found combination.

## Notes

- Companies are de-duplicated within a run and matched against the master by a normalized 10-digit phone number.
- The master file can have multiple sheets — all are read on load, and new companies are appended only to `Sheet2` (kept separate in case `Sheet1` is near Excel's row limit).
- Run with `debug=True` and `use_reloader=False` — the reloader is disabled intentionally to avoid duplicating the background scraper thread.

## Disclaimer

This tool scrapes Google Maps listing data. Make sure your usage complies with Google's Terms of Service and applicable data collection laws before running it at scale.
