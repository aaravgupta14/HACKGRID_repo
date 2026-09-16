import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = ROOT / "models"
OUTPUT_DIR = ROOT / "outputs"

AGMARKNET_URL = "https://api.agmarknet.gov.in/v1/dashboard-data/"
DATAGOV_URL = "https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24"
DATAGOV_API_KEY = os.environ.get(
    "DATA_GOV_API_KEY", "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"
)

COMMODITY_IDS = {"Tomato": 65, "Onion": 23, "Potato": 24}
STATE_IDS = {
    "Karnataka": 16,
    "Maharashtra": 20,
    "Andhra Pradesh": 2,
    "Madhya Pradesh": 19,
    "Uttar Pradesh": 34,
    "Gujarat": 11,
    "Tamil Nadu": 31,
}

TRACKED = [("Tomato", "Karnataka")]
START_DATE = "2022-01-01"
END_DATE = "2025-12-31"

BASELINE_WINDOW = 30
MIN_BASELINE_DAYS = 10
FORECAST_HORIZON = 10
CRASH_DROP = 0.30
SPIKE_RATIO = 1.5
MIN_DISTRICT_COVERAGE = 0.5
TEST_START = "2025-01-01"

RISK_HIGH = 0.60
RISK_WATCH = 0.35

SEVERITY_CAP = 3.0
MOMENTUM_CAP_PCT = 5.0
SCORE_WEIGHTS = {"crash_probability": 0.5, "severity": 0.3, "momentum": 0.2}

MARKETPLACE_DIR = DATA_DIR / "marketplace"
BUYER_TYPES = ["Small processor", "Retailer", "Canteen", "Hotel or restaurant", "Caterer", "Other small business"]
SELLER_TYPES = ["FPO", "Trader", "Aggregator"]
DEFAULT_MATCH_RADIUS_KM = 150
