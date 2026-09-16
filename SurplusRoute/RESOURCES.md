# Won Resources and Traceability

| Resource | Won | How the build stays within it |
| --- | --- | --- |
| Track | Agriculture | Only perishable crop mandi data (arrivals and prices) from Agmarknet and data.gov.in, plus a surplus listing and buyer registry for that produce |
| AI Rights | Predictive & Analytical AI | Numeric time series only: rolling baselines, rule based glut flags, severity and momentum scores, gradient boosting crash forecasts, historical buffer days, weighted buyer match scores. No generative, vision or speech models. Verdict sentences are fixed templates filled with computed numbers |
| AI Capability | Single Agent | One class, `SurplusRouteAgent`, run on request: observe, analyze, forecast, decide, report, and `match_surplus` when a seller lists stock. It only ranks and recommends; it never contacts buyers, places orders, schedules itself or triggers other agents |
| Customer Segment | Small Businesses | Sellers are FPOs, traders and aggregators. Buyers must be small businesses (small processors, retailers, canteens, hotels, caterers) and must confirm this to register |

## Decision trace

| Feature | File | Resource |
| --- | --- | --- |
| Daily arrivals and prices, cached, resumable | `collect.py` | Track |
| District panel and per mandi price series with gap filling | `prepare.py`, `mandi_series.py` | Track, AI Rights |
| 30 day baselines, glut flag when arrivals spike before price fully drops | `features.py`, `scoring.py` | AI Rights |
| Severity, momentum, historical buffer days, glut score | `scoring.py` | AI Rights |
| Crash probability, expected drop, days to bottom | `model.py` | AI Rights |
| Walk forward backtest, false alarm rate | `backtest.py` | AI Rights |
| Single observe to report cycle, ranked alerts, reroute advice | `agent.py` | AI Capability |
| Surplus listing and small business buyer matching | `marketplace.py`, `geo.py`, `agent.py` | Customer Segment, AI Rights |
| Ranked alert dashboard, listing and registry forms | `dashboard.py` | Customer Segment |
| Year models trained only on earlier years, used for past dates | `model.py`, `agent.py` | AI Rights |
| Plain reason and action codes per alert | `agent.py` | AI Capability, Customer Segment |
| English, Kannada and Hindi labels | `i18n.py`, `dashboard.py` | Customer Segment |
| Real small business buyers from public sources, marked as not registered | `public_buyers.py`, `marketplace.py` | Customer Segment |

## Out of scope by design

- Automatic calls, SMS, WhatsApp or email to buyers or sellers
- Automatic deal closing, payments or logistics booking
- Scheduled or self triggered runs, chained or multiple agents
- Large organizations as buyers or data feed customers
- Farmer facing (individual) advice
- e-NAM cross check: no public data API was available, so it is not claimed
