# SurplusRoute

**Predictive early warning for mandi price crashes, built for small agri businesses.**

Hackathon submission by **Team Ghee Podi Dosa**

| Won resource | Our pick |
| --- | --- |
| Track | Agriculture |
| AI Rights | Predictive & Analytical AI |
| AI Capability | Single Agent |
| Customer Segment | Small Businesses |

---

## Steps to run (in order)

The data and trained models are already included, so nothing needs to be downloaded or trained.

**1. Check Python (3.12 or 3.13)**

```bash
python --version
```

**2. Download the code**

```bash
git clone https://github.com/aaravgupta14/HACKGRID_repo.git
```

**3. Go into the project folder**

```bash
cd HACKGRID_repo/SurplusRoute
```

**4. Install the packages**

```bash
pip install -r requirements.txt
```

**5. Start the dashboard**

```bash
python -m streamlit run dashboard.py
```

**6. Open http://localhost:8501 in your browser.** Press `Ctrl + C` in the terminal to stop.

Full details, a demo walkthrough and troubleshooting are below.

---

## The problem

When too much of a perishable crop like tomato reaches the mandis at once, prices crash within days. FPOs, traders and aggregators find out only after the fall, when their stock is already rotting or selling at a loss.

## Our solution

SurplusRoute reads daily government mandi data and:

1. **Warns early.** It flags districts heading into a glut before the price crashes.
2. **Predicts the fall.** It gives the chance of a 30% price crash in the next 10 days, how far the price may fall, and how many days are left to act.
3. **Finds a way out.** It shows safer nearby markets and matches the surplus to nearby small business buyers such as canteens, hotels, retailers and small processors.
4. **Keeps people in control.** The AI only advises. A deal is booked only when the seller taps Confirm booking.

It works in English, Kannada and Hindi.

---

## Quick start for judges (about 5 minutes)

The repository already contains the processed data and the trained models, so you do **not** need to download data or train anything to see the app.

### Step 1: Check Python

You need Python 3.12 or 3.13.

```bash
python --version
```

If it is missing, install it from https://www.python.org/downloads/ and tick "Add Python to PATH" during install.

### Step 2: Get the code

```bash
git clone https://github.com/aaravgupta14/HACKGRID_repo.git
```

```bash
cd HACKGRID_repo/SurplusRoute
```

If you received a zipped folder, unzip it and open a terminal inside the folder that contains `dashboard.py`.

### Step 3: Install the packages

```bash
pip install -r requirements.txt
```

### Step 4: Start the dashboard

```bash
python -m streamlit run dashboard.py
```

### Step 5: Open it

Go to http://localhost:8501 in your browser. It usually opens by itself.

To stop the app, press `Ctrl + C` in the terminal.

---

## Demo walkthrough

Follow this path to see every feature in about 3 minutes.

| # | Where | What to do | What you will see |
| --- | --- | --- | --- |
| 1 | Left sidebar | Choose a language, crop Tomato and a market day | The whole app updates for that day |
| 2 | Alerts | Scroll the page | Risk tiles, the agent's 5 steps, a Karnataka risk map, ranked district alerts with chance of price fall and days left to act |
| 3 | Alerts | Scroll to the deep dive | Supply and price charts with the forecast line |
| 4 | Alerts | Tap **Sell my extra stock** on an alert | Jumps to the Sell page with that district filled in |
| 5 | Sell | Fill crop, quantity, grade and price, optionally add a photo, and submit | A fair price hint, then a ranked list of matching buyers |
| 6 | Sell | Look at a buyer card | Phone shows "Hidden until deal is booked", Verified badge, trust line |
| 7 | Sell | Tap **Book with protection** | A deal slip with total, 2% SurplusRoute fee and pickup time |
| 8 | Deal slip | Tap **Confirm booking** | Booking saved and the buyer's phone number is revealed |
| 9 | Join as buyer | Register a business with a Udyam number like `UDYAM-KR-03-0012345` or a 14 digit FSSAI number | Invalid formats are rejected |
| 10 | How it works | Read the page | How the four resources are used, and backtest proof |

Tip: pick a past market day in 2023 or 2024 in the sidebar to see how the alerts looked before real price crashes.

---

## Optional: run from the terminal

See the ranked alerts for a day without the dashboard:

```bash
python -m surplusroute.run_agent --date 2023-08-20
```

Replay how early the model warned before past crashes in one district:

```bash
python -m surplusroute.backtest --district Kolar --start 2023-08-01 --end 2023-09-30
```

---

## Optional: rebuild everything from scratch

Only needed if you want fresh data or to retrain. Run these in order from the folder that contains `dashboard.py`.

| Step | Command | What it does | Time |
| --- | --- | --- | --- |
| 1 | `python -m surplusroute.collect` | Downloads daily arrivals and prices from government APIs | Hours (rate limits), resumable |
| 2 | `python -m surplusroute.prepare` | Cleans data into a district by day table | Seconds |
| 3 | `python -m surplusroute.mandi_series` | Builds daily price series per mandi | Seconds |
| 4 | `python -m surplusroute.model` | Trains the prediction models and writes a test report | About 1 minute |
| 5 | `python -m surplusroute.backtest` | Replays 2023 to 2026 to measure early warnings | A few minutes |
| 6 | `python -m streamlit run dashboard.py` | Starts the dashboard | Seconds |

```bash
python -m surplusroute.collect
```

```bash
python -m surplusroute.prepare
```

```bash
python -m surplusroute.mandi_series
```

```bash
python -m surplusroute.model
```

```bash
python -m surplusroute.backtest
```

```bash
python -m streamlit run dashboard.py
```

If the download stops, run step 1 again. It continues from where it stopped.

The price API uses a shared sample key that is slow. For faster downloads, create a free account at data.gov.in, copy your API key, and set it before step 1.

Windows PowerShell:

```bash
$env:DATA_GOV_API_KEY="your_key_here"
```

macOS or Linux:

```bash
export DATA_GOV_API_KEY="your_key_here"
```

### Command options

| Command | Option | Default | Meaning |
| --- | --- | --- | --- |
| `collect` | `--source` | `all` | `arrivals`, `prices` or `all` |
| `collect` | `--start`, `--end` | `2022-01-01`, `2026-09-16` | Date range |
| `collect` | `--workers` | `2` | Parallel downloads, use 1 if you hit rate limits |
| `backtest` | `--years` | `2023 2024 2025 2026` | Years to replay |
| `backtest` | `--district`, `--start`, `--end` | none | Daily timeline for one district |
| `run_agent` | `--commodity`, `--state` | `Tomato`, `Karnataka` | Crop and state |
| `run_agent` | `--date` | latest date | Market day |

---

## How we use the four won resources

| Resource | How SurplusRoute uses it |
| --- | --- |
| **Agriculture** | Perishable crop mandi arrivals and prices from Agmarknet and data.gov.in |
| **Predictive AI** | Gradient boosting models forecast the chance, size and timing of a price crash |
| **Analytical AI** | Baselines, glut flags, severity and momentum scores, backtesting and buyer match scores |
| **Single Agent** | One `SurplusRouteAgent` runs one cycle when asked: observe, analyze, forecast, decide, report. It never books, messages or runs by itself |
| **Small Businesses** | Sellers are FPOs, traders and aggregators. Buyers are small processors, retailers, canteens, hotels and caterers, verified by Udyam or FSSAI number format |

Detailed traceability is in [RESOURCES.md](RESOURCES.md).

## How the AI works

**Analytical part** (`features.py`, `scoring.py`)

- Normal level: average of the last 30 days.
- Glut flag: arrivals at least 1.5 times normal while price has not yet fallen 30%.
- Severity score: 0 at normal arrivals, 100 at 3 times normal.
- Momentum score: speed of price fall over 3 days.
- Buffer days: how long similar past crashes took to hit bottom.
- Glut score: 50% crash chance, 30% severity, 20% momentum.
- Buyer match: 40% distance, 35% quantity the buyer can take, 25% price fit.

**Predictive part** (`model.py`)

`GlutForecaster` uses three scikit-learn gradient boosting models trained on 16 signals such as supply against normal, price change over 3 and 7 days, volatility, statewide supply and time of year.

| Model | Predicts |
| --- | --- |
| `HistGradientBoostingClassifier` | Chance the price falls 30% or more within 10 days |
| `HistGradientBoostingRegressor` | How far the price may fall |
| `HistGradientBoostingRegressor` (absolute error) | Days until the price hits bottom |

For past dates the dashboard uses models trained only on earlier years, so old predictions never see the future.

**Single agent** (`agent.py`)

`SurplusRouteAgent` observes the chosen day's data, analyzes glut signals, forecasts crash risk, decides a risk level, reason and action for each district, and reports a ranked list. `match_surplus` ranks buyers for a listing. It contains no booking, messaging or scheduling code.

## Results (Tomato, Karnataka)

| Metric | Value |
| --- | --- |
| Big price falls caught in 2023 to 2026 backtest | 206 of 225 (92%) |
| Median warning before a 15% price fall | 11 days |
| Median warning before the bottom | 16.5 days |
| Precision of Act now alerts on 2025+ test data | 36%, against 13% for a simple rule |
| Error in predicted days to bottom | 2.5 days |
| False alarm rate | 59% |

We show the false alarm rate openly. For a seller, an unneeded early warning costs far less than being caught in a crash.

## Data sources

| Data | Source | Level |
| --- | --- | --- |
| Arrivals (tonnes) | Agmarknet 2.0 public dashboard API | District, daily |
| Min, max and modal price | data.gov.in, Variety-wise Daily Market Prices | Mandi, daily |
| Public buyers | Public business listings, checked 16 Sep 2026 | Business |

## Tech stack

Python, pandas, NumPy, scikit-learn, Streamlit, Plotly, OpenStreetMap, Pillow.

## Project structure

```
.
├── dashboard.py                Streamlit dashboard
├── requirements.txt            Python packages
├── RESOURCES.md                Traceability to the four won resources
├── .streamlit/config.toml      Theme
├── assets/                     Product and team logos
├── surplusroute/
│   ├── config.py               Crops, thresholds, API settings
│   ├── collect.py              Downloads arrivals and prices
│   ├── prepare.py              District by day table
│   ├── mandi_series.py         Per mandi price series
│   ├── features.py             Signals and crash labels
│   ├── scoring.py              Glut flag and scores
│   ├── model.py                Prediction models
│   ├── backtest.py             Replay over past years
│   ├── agent.py                SurplusRouteAgent (single agent)
│   ├── marketplace.py          Listings, buyers, matching, bookings
│   ├── public_buyers.py        Real small businesses from public listings
│   ├── geo.py                  District locations and distances
│   ├── i18n.py                 English, Kannada and Hindi text
│   └── run_agent.py            Terminal alerts
├── data/                       Raw and processed data
├── models/                     Trained models
└── outputs/                    Model report and backtest results
```

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `python` is not recognized | Try `py` or `python3` instead of `python` |
| `streamlit` is not recognized | Use `python -m streamlit run dashboard.py` |
| Port 8501 already in use | `python -m streamlit run dashboard.py --server.port 8502` |
| `pip install` fails | Upgrade pip with `python -m pip install --upgrade pip`, then retry |
| Map is blank | Check the internet connection; map tiles load from OpenStreetMap |
| 429 Too Many Requests while collecting | Wait, use `--workers 1`, set your own `DATA_GOV_API_KEY`, rerun |

## Limitations

- Included data and models cover tomato in Karnataka. Onion and potato are set up but their data is not downloaded yet.
- Arrivals are at district level because mandi level arrivals on Agmarknet need a CAPTCHA.
- Verified means the Udyam or FSSAI number format is valid, not checked with the government registry.
- Trust scores on registered buyers are sample data and are labelled as such.
- Payment holding is marked coming soon through a licensed payment partner; no money is handled.
- Listings, buyers and bookings are saved in local CSV files.

---

Created by Team Ghee Podi Dosa
