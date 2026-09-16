import math

DISTRICT_COORDINATES = {
    "bagalkot": (16.18, 75.70),
    "ballari": (15.14, 76.92),
    "belagavi": (15.85, 74.50),
    "bengaluru": (12.97, 77.59),
    "bengaluru rural": (13.29, 77.54),
    "bengaluru south": (12.72, 77.28),
    "bidar": (17.91, 77.52),
    "chamarajanagar": (11.92, 76.94),
    "chikkaballapur": (13.43, 77.73),
    "chikkamagaluru": (13.32, 75.77),
    "chitradurga": (14.23, 76.40),
    "dakshina kannada": (12.91, 74.86),
    "davangere": (14.46, 75.92),
    "dharwad": (15.46, 75.01),
    "gadag": (15.43, 75.63),
    "hassan": (13.01, 76.10),
    "haveri": (14.79, 75.40),
    "kalaburagi": (17.33, 76.83),
    "kodagu": (12.42, 75.74),
    "kolar": (13.14, 78.13),
    "koppal": (15.35, 76.15),
    "mandya": (12.52, 76.90),
    "mysuru": (12.30, 76.64),
    "raichur": (16.21, 77.36),
    "shivamogga": (13.93, 75.57),
    "tumakuru": (13.34, 77.10),
    "udupi": (13.34, 74.75),
    "uttara kannada": (14.81, 74.13),
    "vijayanagara": (15.27, 76.39),
    "vijayapura": (16.83, 75.71),
    "yadgir": (16.77, 77.14),
}


def district_key(name):
    return " ".join(str(name or "").lower().split())


def distance_km(district_a, district_b):
    a = DISTRICT_COORDINATES.get(district_key(district_a))
    b = DISTRICT_COORDINATES.get(district_key(district_b))
    if district_key(district_a) == district_key(district_b):
        return 0.0
    if a is None or b is None:
        return None
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return round(2 * 6371 * math.asin(math.sqrt(h)), 1)


def known_districts():
    return sorted(name.title() for name in DISTRICT_COORDINATES)
