# SurplusRoute: Predictive Mandi-Glut Agent

A single predictive and analytical AI agent that warns small agri businesses (FPOs, traders, aggregators) that a perishable crop is heading into a glut, before the price crash, and connects their surplus to nearby small business buyers.

## Data sources

| Signal | Source | Granularity |
| --- | --- | --- |
| Arrivals (tonnes) | Agmarknet 2.0 public dashboard API (`api.agmarknet.gov.in`) | District, daily |
| Min / max / modal price (Rs/quintal) | data.gov.in, Variety-wise Daily Market Prices (Agmarknet) | Mandi, daily |

Mandi level arrivals sit behind a CAPTCHA on Agmarknet, so arrivals are used at district level and prices at mandi level. e-NAM has no public data API, so no e-NAM cross check is made.

## Pipeline

| Step | Module | What it does |
| --- | --- | --- |
| 1 | `collect.py` | Downloads daily arrivals and prices, rate limited, resumable |
| 2 | `prepare.py` | District by day panel, district name matching, gap filling |
| 3 | `mandi_series.py` | Per mandi daily price series with gap filling |
| 4 | `features.py` | Rolling baselines, arrival spikes, price momentum, statewide spread, crash labels |
| 5 | `scoring.py` | Glut flag, severity, momentum, historical buffer days, glut score |
| 6 | `model.py` | Crash probability, expected drop and days to bottom, time based test |
| 7 | `backtest.py` | Walk forward replay, lead time before real crashes, false alarm rate |
| 8 | `agent.py` | `SurplusRouteAgent`: observe, analyze, forecast, decide, report, match surplus |
| 9 | `marketplace.py`, `geo.py` | Surplus listings, small business buyer registry, distance and match scoring |
| 10 | `run_agent.py` | Ranked alerts in the terminal and as JSON |
| 11 | `dashboard.py` | Streamlit dashboard |

## Run

```bash
pip install -r requirements.txt
```

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
python -m surplusroute.backtest --district Kolar --start 2023-08-01 --end 2023-09-30
```

```bash
python -m surplusroute.run_agent --date 2023-08-20
```

```bash
streamlit run dashboard.py
```

Set `DATA_GOV_API_KEY` to your own free data.gov.in key; the shared sample key is heavily rate limited.

## Definitions

- Baseline: trailing 30 day mean, excluding the current day.
- Glut flag: arrivals at least 1.5x baseline while price is still less than 30% below baseline.
- Severity score: arrivals above baseline, 0 at baseline, 100 at 3x.
- Momentum score: price fall per day over 3 days, 100 at 5% per day.
- Buffer days: 25th to 75th percentile of days to bottom in past flagged crashes of similar severity, using only history before the alert date.
- Crash ahead: modal price falls at least 30% within the next 10 days.
- HIGH: crash probability at least 0.60. WATCH: at least 0.35, or glut flagged.
- Glut score: 50% crash probability, 30% severity, 20% momentum.
- Buyer match score: 40% distance, 35% quantity the buyer can absorb, 25% price fit.
