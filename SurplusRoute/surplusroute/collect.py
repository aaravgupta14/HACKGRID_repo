import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import requests

from surplusroute import config

_lock = threading.Lock()
_session = requests.Session()
_session.headers.update({"User-Agent": "SurplusRoute-DataCollector/1.0"})


class Throttle:
    def __init__(self, min_interval):
        self.min_interval = min_interval
        self.next_slot = 0.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.monotonic()
            delay = self.next_slot - now
            self.next_slot = max(now, self.next_slot) + self.min_interval
        if delay > 0:
            time.sleep(delay)

    def pause(self, seconds):
        with self.lock:
            self.next_slot = max(self.next_slot, time.monotonic() + seconds)


THROTTLES = {"arrivals": Throttle(3.0), "prices": Throttle(1.0)}


def _backoff_seconds(response, attempt):
    retry_after = response.headers.get("Retry-After") if response is not None else None
    if retry_after and retry_after.isdigit():
        return int(retry_after)
    return min(300, 15 * 2 ** attempt)


def _request(throttle, method, url, attempts=8, **kwargs):
    for attempt in range(attempts):
        throttle.wait()
        response = None
        try:
            response = _session.request(method, url, timeout=90, **kwargs)
            if response.status_code == 200:
                return response.json()
        except (requests.RequestException, ValueError):
            pass
        wait = _backoff_seconds(response, attempt)
        throttle.pause(wait)
    raise RuntimeError(f"{method} {url} failed after {attempts} attempts")


def _post_json(url, body):
    return _request(THROTTLES["arrivals"], "POST", url, json=body)


def _get_json(url, params):
    payload = _request(THROTTLES["prices"], "GET", url, params=params)
    if "records" not in payload:
        raise RuntimeError(f"Unexpected payload for {params}")
    return payload


def fetch_arrivals(commodity, state, day):
    body = {
        "dashboard": "cumm_arrival_sp",
        "from_date": day.isoformat(),
        "to_date": day.isoformat(),
        "commodity": [config.COMMODITY_IDS[commodity]],
        "state": [config.STATE_IDS[state]],
        "format": "json",
        "page": 1,
        "limit": 500,
    }
    payload = _post_json(config.AGMARKNET_URL, body)
    records = (payload.get("data") or {}).get("records") or []
    return [
        {
            "date": day.isoformat(),
            "state": r.get("state_name"),
            "district": r.get("district_name"),
            "arrival_tonnes": r.get("as_on"),
        }
        for r in records
    ]


def fetch_prices(commodity, state, day):
    rows, offset, total = [], 0, None
    while total is None or offset < total:
        params = {
            "api-key": config.DATAGOV_API_KEY,
            "format": "json",
            "limit": 10,
            "offset": offset,
            "filters[Commodity]": commodity,
            "filters[State]": state,
            "filters[Arrival_Date]": day.strftime("%d/%m/%Y"),
        }
        payload = _get_json(config.DATAGOV_URL, params)
        total = int(payload.get("total") or 0)
        batch = payload.get("records") or []
        if not batch:
            break
        rows.extend(
            {
                "date": day.isoformat(),
                "state": r.get("State"),
                "district": r.get("District"),
                "market": r.get("Market"),
                "variety": r.get("Variety"),
                "grade": r.get("Grade"),
                "min_price": r.get("Min_Price"),
                "max_price": r.get("Max_Price"),
                "modal_price": r.get("Modal_Price"),
            }
            for r in batch
        )
        offset += len(batch)
    return rows


SOURCES = {"arrivals": fetch_arrivals, "prices": fetch_prices}


def cache_path(source, commodity, state):
    folder = config.RAW_DIR / source
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{commodity}_{state.replace(' ', '_')}.jsonl"


def completed_days(path):
    if not path.exists():
        return set()
    done = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                done.add(json.loads(line)["date"])
    return done


def date_range(start, end):
    current, stop = date.fromisoformat(start), date.fromisoformat(end)
    while current <= stop:
        yield current
        current += timedelta(days=1)


def collect(source, commodity, state, start, end, workers):
    path = cache_path(source, commodity, state)
    done = completed_days(path)
    pending = [d for d in date_range(start, end) if d.isoformat() not in done]
    print(f"[{source}] {commodity}/{state}: {len(done)} cached, {len(pending)} to fetch", flush=True)
    fetcher = SOURCES[source]
    finished = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetcher, commodity, state, d): d for d in pending}
        for future in as_completed(futures):
            day = futures[future]
            try:
                records = future.result()
            except RuntimeError as error:
                print(f"[{source}] skipped {day}: {error}", flush=True)
                continue
            with _lock, path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"date": day.isoformat(), "records": records}) + "\n")
            finished += 1
            if finished % 50 == 0:
                print(f"[{source}] {commodity}/{state}: {finished}/{len(pending)}", flush=True)
    print(f"[{source}] {commodity}/{state}: done", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=[*SOURCES, "all"], default="all")
    parser.add_argument("--start", default=config.START_DATE)
    parser.add_argument("--end", default=config.END_DATE)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    sources = list(SOURCES) if args.source == "all" else [args.source]
    for commodity, state in config.TRACKED:
        for source in sources:
            collect(source, commodity, state, args.start, args.end, args.workers)


if __name__ == "__main__":
    main()
