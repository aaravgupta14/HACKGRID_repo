import uuid
from datetime import datetime

import numpy as np
import pandas as pd

from surplusroute import config
from surplusroute.geo import distance_km
from surplusroute.public_buyers import PUBLIC_BUYERS, PUBLIC_BUYERS_CHECKED_ON

LISTING_COLUMNS = [
    "listing_id", "seller_name", "seller_type", "contact_phone", "contact_email", "crop", "state", "district",
    "quantity_qtl", "asking_price_per_qtl", "available_until", "alert_risk_level", "alert_crash_probability",
    "created_at",
]
BUYER_COLUMNS = [
    "buyer_id", "business_name", "business_type", "state", "district", "crops", "weekly_capacity_qtl",
    "max_price_per_qtl", "max_distance_km", "contact_name", "contact_phone", "contact_email",
    "small_business_confirmed", "registered_at",
]
DIRECTORY_COLUMNS = BUYER_COLUMNS + ["address", "source_url", "listing_status", "checked_on"]


def _path(name):
    config.MARKETPLACE_DIR.mkdir(parents=True, exist_ok=True)
    return config.MARKETPLACE_DIR / f"{name}.csv"


def _load(name, columns):
    path = _path(name)
    if not path.exists():
        return pd.DataFrame(columns=columns)
    return pd.read_csv(path, dtype={"contact_phone": str})


def _append(name, columns, record):
    frame = _load(name, columns)
    new_row = pd.DataFrame([record], columns=columns)
    frame = new_row if frame.empty else pd.concat([frame, new_row], ignore_index=True)
    frame.to_csv(_path(name), index=False)
    return record


def load_listings():
    return _load("listings", LISTING_COLUMNS)


def public_buyers():
    rows = []
    for index, entry in enumerate(PUBLIC_BUYERS):
        rows.append({
            **entry,
            "buyer_id": f"public{index + 1}",
            "weekly_capacity_qtl": np.nan,
            "max_price_per_qtl": np.nan,
            "max_distance_km": float(config.DEFAULT_MATCH_RADIUS_KM),
            "contact_name": "",
            "small_business_confirmed": True,
            "registered_at": "",
            "listing_status": "public",
            "checked_on": PUBLIC_BUYERS_CHECKED_ON,
        })
    return pd.DataFrame(rows, columns=DIRECTORY_COLUMNS)


def load_buyers(include_public=True):
    registered = _load("buyers", BUYER_COLUMNS).reindex(columns=DIRECTORY_COLUMNS)
    registered["listing_status"] = "registered"
    frames = [registered] + ([public_buyers()] if include_public else [])
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=DIRECTORY_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def add_listing(seller_name, seller_type, contact_phone, contact_email, crop, state, district, quantity_qtl,
                asking_price_per_qtl, available_until, alert_risk_level=None, alert_crash_probability=None):
    _require(str(seller_name).strip(), "name_required")
    _require(seller_type in config.SELLER_TYPES, "seller_type_invalid")
    _require(str(contact_phone).strip() or str(contact_email).strip(), "contact_required")
    _require(float(quantity_qtl) > 0, "quantity_required")
    _require(float(asking_price_per_qtl) > 0, "price_required")
    return _append("listings", LISTING_COLUMNS, {
        "listing_id": uuid.uuid4().hex[:8],
        "seller_name": str(seller_name).strip(),
        "seller_type": seller_type,
        "contact_phone": str(contact_phone).strip(),
        "contact_email": str(contact_email).strip(),
        "crop": crop,
        "state": state,
        "district": district,
        "quantity_qtl": float(quantity_qtl),
        "asking_price_per_qtl": float(asking_price_per_qtl),
        "available_until": str(available_until),
        "alert_risk_level": alert_risk_level,
        "alert_crash_probability": alert_crash_probability,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })


def add_buyer(business_name, business_type, state, district, crops, weekly_capacity_qtl, max_price_per_qtl,
              max_distance_km, contact_name, contact_phone, contact_email, small_business_confirmed):
    _require(str(business_name).strip(), "name_required")
    _require(business_type in config.BUYER_TYPES, "buyer_type_invalid")
    _require(bool(small_business_confirmed), "small_business_required")
    _require(len(crops) > 0, "crop_required")
    _require(str(contact_phone).strip() or str(contact_email).strip(), "contact_required")
    _require(float(weekly_capacity_qtl) > 0, "capacity_required")
    return _append("buyers", BUYER_COLUMNS, {
        "buyer_id": uuid.uuid4().hex[:8],
        "business_name": str(business_name).strip(),
        "business_type": business_type,
        "state": state,
        "district": district,
        "crops": ";".join(crops),
        "weekly_capacity_qtl": float(weekly_capacity_qtl),
        "max_price_per_qtl": float(max_price_per_qtl),
        "max_distance_km": float(max_distance_km or config.DEFAULT_MATCH_RADIUS_KM),
        "contact_name": str(contact_name).strip(),
        "contact_phone": str(contact_phone).strip(),
        "contact_email": str(contact_email).strip(),
        "small_business_confirmed": True,
        "registered_at": datetime.now().isoformat(timespec="seconds"),
    })


def match_buyers(listing, buyers, top_n=5):
    if buyers.empty:
        return pd.DataFrame()
    crop = str(listing["crop"]).lower()
    candidates = buyers[
        buyers["crops"].fillna("").str.lower().str.split(";").apply(lambda crops: crop in crops)
        & buyers["small_business_confirmed"].astype(str).str.lower().isin(["true", "1"])
    ].copy()
    if candidates.empty:
        return candidates
    quantity = float(listing["quantity_qtl"])
    asking = float(listing["asking_price_per_qtl"])
    candidates["max_distance_km"] = candidates["max_distance_km"].fillna(config.DEFAULT_MATCH_RADIUS_KM)
    candidates["distance_km"] = candidates["district"].apply(lambda d: distance_km(listing["district"], d))
    candidates = candidates[candidates["distance_km"].notna()]
    candidates = candidates[candidates["distance_km"] <= candidates["max_distance_km"]]
    known_price = candidates["max_price_per_qtl"].notna()
    candidates = candidates[~known_price | (candidates["max_price_per_qtl"] >= asking * 0.8)]
    if candidates.empty:
        return candidates
    candidates["can_absorb_qtl"] = candidates["weekly_capacity_qtl"].clip(upper=quantity)
    distance_fit = 1 - candidates["distance_km"] / candidates["max_distance_km"].where(candidates["max_distance_km"] > 0, 1)
    quantity_fit = (candidates["can_absorb_qtl"] / quantity).fillna(0.5)
    price_fit = ((candidates["max_price_per_qtl"] - asking * 0.8) / (asking * 0.2)).clip(0, 1).fillna(0.5)
    candidates["price_gap_per_qtl"] = candidates["max_price_per_qtl"] - asking
    registered_bonus = np.where(candidates["listing_status"] == "registered", 10, 0)
    candidates["match_score"] = (100 * (0.4 * distance_fit + 0.35 * quantity_fit + 0.25 * price_fit) * 0.9
                                 + registered_bonus).round(1)
    columns = ["business_name", "business_type", "district", "address", "distance_km", "can_absorb_qtl",
               "max_price_per_qtl", "price_gap_per_qtl", "match_score", "contact_name", "contact_phone",
               "contact_email", "listing_status", "source_url"]
    return candidates.sort_values("match_score", ascending=False)[columns].head(top_n).reset_index(drop=True)
