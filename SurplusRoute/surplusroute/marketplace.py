import hashlib
import io
import re
import uuid
from datetime import datetime

import numpy as np
import pandas as pd

from surplusroute import config
from surplusroute.geo import distance_km
from surplusroute.public_buyers import PUBLIC_BUYERS, PUBLIC_BUYERS_CHECKED_ON

PLATFORM_FEE_RATE = 0.02
UDYAM_PATTERN = re.compile(r"^UDYAM-[A-Z]{2}-\d{2}-\d{7}$")
FSSAI_PATTERN = re.compile(r"^\d{14}$")

LISTING_COLUMNS = [
    "listing_id", "seller_name", "seller_type", "contact_phone", "contact_email", "crop", "state", "district",
    "quantity_qtl", "grade", "asking_price_per_qtl", "available_until", "alert_risk_level",
    "alert_crash_probability", "photo_path", "photo_timestamp", "created_at",
]
BUYER_COLUMNS = [
    "buyer_id", "business_name", "business_type", "state", "district", "crops", "weekly_capacity_qtl",
    "max_price_per_qtl", "max_distance_km", "contact_name", "contact_phone", "contact_email",
    "business_id", "business_id_type", "small_business_confirmed", "registered_at",
]
DIRECTORY_COLUMNS = BUYER_COLUMNS + ["address", "source_url", "listing_status", "checked_on"]
BOOKING_COLUMNS = [
    "booking_id", "listing_id", "buyer_id", "buyer_name", "crop", "grade", "quantity_qtl", "price_per_kg",
    "total_rupees", "fee_rupees", "seller_receives_rupees", "pickup_at", "status", "confirmed_by_user", "booked_at",
]


def _path(name):
    config.MARKETPLACE_DIR.mkdir(parents=True, exist_ok=True)
    return config.MARKETPLACE_DIR / f"{name}.csv"


def _load(name, columns):
    path = _path(name)
    if not path.exists():
        return pd.DataFrame(columns=columns)
    frame = pd.read_csv(path, dtype={"contact_phone": str, "business_id": str})
    return frame.reindex(columns=columns)


def _append(name, columns, record):
    frame = _load(name, columns)
    new_row = pd.DataFrame([record], columns=columns)
    frame = new_row if frame.empty else pd.concat([frame, new_row], ignore_index=True)
    frame.to_csv(_path(name), index=False)
    return record


def load_listings():
    return _load("listings", LISTING_COLUMNS)


def load_bookings():
    return _load("bookings", BOOKING_COLUMNS)


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
            "business_id": "",
            "business_id_type": "",
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


def business_id_type(value):
    text = str(value or "").strip().upper().replace(" ", "")
    if UDYAM_PATTERN.match(text):
        return "Udyam"
    if FSSAI_PATTERN.match(text):
        return "FSSAI"
    return None


def is_verified(buyer):
    return buyer.get("listing_status") == "registered" and str(buyer.get("business_id_type") or "") in {"Udyam", "FSSAI"}


def sample_trust(buyer):
    if buyer.get("listing_status") != "registered":
        return None
    seed = int(hashlib.sha256(str(buyer.get("buyer_id")).encode()).hexdigest(), 16)
    return {
        "rating": round(4.2 + (seed % 8) / 10, 1),
        "deals": 5 + seed % 36,
        "disputes": (seed // 7) % 2,
    }


def deal_totals(quantity_qtl, price_per_qtl):
    total = float(quantity_qtl) * float(price_per_qtl)
    fee = round(total * PLATFORM_FEE_RATE, 2)
    return {"total": round(total, 2), "fee": fee, "seller_receives": round(total - fee, 2)}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _save_stamped_photo(listing_id, photo_bytes, stamp):
    from PIL import Image, ImageDraw

    folder = config.MARKETPLACE_DIR / "photos"
    folder.mkdir(parents=True, exist_ok=True)
    image = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    image.thumbnail((1600, 1600))
    draw = ImageDraw.Draw(image)
    label = f"SurplusRoute  {stamp}"
    box_height = max(28, image.height // 18)
    draw.rectangle([0, image.height - box_height, image.width, image.height], fill=(18, 61, 26))
    draw.text((12, image.height - box_height + box_height // 4), label, fill=(255, 255, 255))
    path = folder / f"{listing_id}.jpg"
    image.save(path, quality=88)
    return path


def add_listing(seller_name, seller_type, contact_phone, contact_email, crop, state, district, quantity_qtl,
                asking_price_per_qtl, available_until, alert_risk_level=None, alert_crash_probability=None,
                grade="A", photo_bytes=None):
    _require(str(seller_name).strip(), "name_required")
    _require(seller_type in config.SELLER_TYPES, "seller_type_invalid")
    _require(str(contact_phone).strip() or str(contact_email).strip(), "contact_required")
    _require(float(quantity_qtl) > 0, "quantity_required")
    _require(float(asking_price_per_qtl) > 0, "price_required")
    _require(grade in config.GRADES, "grade_invalid")
    listing_id = uuid.uuid4().hex[:8]
    now = datetime.now()
    photo_path, photo_timestamp = "", ""
    if photo_bytes:
        photo_timestamp = now.strftime("%d %b %Y %H:%M")
        photo_path = str(_save_stamped_photo(listing_id, photo_bytes, photo_timestamp))
    return _append("listings", LISTING_COLUMNS, {
        "listing_id": listing_id,
        "seller_name": str(seller_name).strip(),
        "seller_type": seller_type,
        "contact_phone": str(contact_phone).strip(),
        "contact_email": str(contact_email).strip(),
        "crop": crop,
        "state": state,
        "district": district,
        "quantity_qtl": float(quantity_qtl),
        "grade": grade,
        "asking_price_per_qtl": float(asking_price_per_qtl),
        "available_until": str(available_until),
        "alert_risk_level": alert_risk_level,
        "alert_crash_probability": alert_crash_probability,
        "photo_path": photo_path,
        "photo_timestamp": photo_timestamp,
        "created_at": now.isoformat(timespec="seconds"),
    })


def add_buyer(business_name, business_type, state, district, crops, weekly_capacity_qtl, max_price_per_qtl,
              max_distance_km, contact_name, contact_phone, contact_email, business_id):
    _require(str(business_name).strip(), "name_required")
    _require(business_type in config.BUYER_TYPES, "buyer_type_invalid")
    id_type = business_id_type(business_id)
    _require(id_type is not None, "business_id_invalid")
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
        "business_id": str(business_id).strip().upper().replace(" ", ""),
        "business_id_type": id_type,
        "small_business_confirmed": True,
        "registered_at": datetime.now().isoformat(timespec="seconds"),
    })


def create_booking(listing, buyer, pickup_at, confirmed_by_user=False):
    if confirmed_by_user is not True:
        raise PermissionError("booking_requires_user_confirmation")
    totals = deal_totals(listing["quantity_qtl"], listing["asking_price_per_qtl"])
    record = {
        "booking_id": uuid.uuid4().hex[:8],
        "listing_id": listing["listing_id"],
        "buyer_id": buyer["buyer_id"],
        "buyer_name": buyer["business_name"],
        "crop": listing["crop"],
        "grade": listing.get("grade") if pd.notna(listing.get("grade")) else "",
        "quantity_qtl": float(listing["quantity_qtl"]),
        "price_per_kg": round(float(listing["asking_price_per_qtl"]) / 100, 2),
        "total_rupees": totals["total"],
        "fee_rupees": totals["fee"],
        "seller_receives_rupees": totals["seller_receives"],
        "pickup_at": str(pickup_at),
        "status": "booked",
        "confirmed_by_user": True,
        "booked_at": datetime.now().isoformat(timespec="seconds"),
    }
    _append("bookings", BOOKING_COLUMNS, record)
    return record


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
    columns = ["buyer_id", "business_name", "business_type", "district", "address", "distance_km", "can_absorb_qtl",
               "max_price_per_qtl", "price_gap_per_qtl", "match_score", "contact_name", "contact_phone",
               "contact_email", "business_id_type", "listing_status", "source_url"]
    return candidates.sort_values("match_score", ascending=False)[columns].head(top_n).reset_index(drop=True)
