"""
Edinburgh Fringe 2026 — data pipeline
--------------------------------------
Fetches all shows from the GraphQL API, flattens them into a clean
DataFrame, geocodes unique venues, and saves:

  fringe_shows.json        raw API responses (all pages)
  fringe_shows.csv         flat show-level table (one row per show)
  fringe_performances.csv  flat performance-level table (one row per slot)
  fringe_venues.csv        unique venues with lat/lng
  fringe_shows.geojson     shows with venue coordinates (for mapping)

Usage:
  pip install requests pandas tqdm geopy
  python fringe_fetch.py

The token is long-lived (expires ~2027) but if it expires, grab a fresh
one by opening https://www.edfringe.com, opening DevTools → Network,
filtering for "graphql", and copying the Authorization header value.
"""

import json
import time
import re
from pathlib import Path

import requests
import pandas as pd
from tqdm import tqdm
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TOKEN = (
    "eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9"
    ".eyJ1bmlxdWVfbmFtZSI6IiIsImVtYWlsIjoiYW5vbnltb3VzIiwibmFtZWlkIjoiMCIs"
    "InJvbGUiOiJhbm9ueW1vdXMiLCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLz"
    "IwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL2lzcGVyc2lzdGVudCI6IkZhbHNlIiwiaHR0cDov"
    "L3NjaGVtYXMueG1sc29hcC5vcmcvd3MvMjAwNS8wNS9pZGVudGl0eS9jbGFpbXMvYW5vbn"
    "ltb3VzIjoiVHJ1ZSIsImlkcCI6ImxvY2FsIiwiYXV0aF90aW1lIjoiMjAyNi0wNC0wNSAy"
    "MDo0OToyOVoiLCJ1c2VyX2FnZW50Ijoid2ViIiwibmJmIjoxNzc1NDIyMTY5LCJleHAiOj"
    "E4MDY4NzI2NjksImlhdCI6MTc3NTQyMjE2OSwiaXNzIjoiaHR0cHM6Ly9sb2NhbGhvc3Q6"
    "NzE3MS8iLCJhdWQiOiJodHRwczovL2xvY2FsaG9zdDo3MTcxL2dyYXBocWwifQ"
    ".dikMDFHani1SRQ4dM1OYdDeo0j_YMcYWhzePFc5dYSKHS1_1wyP6sbgm8ZvCEc2G5M8"
    "-xK_hDdJ7wBUKeEmQ8Q"
)

ENDPOINT = "https://edfringe-tikketr-web-api.equhost.com/graphql"
PER_PAGE = 50
OUTPUT_DIR = Path(".")
GEOCODE_DELAY = 1.1  # seconds between geocode requests (Nominatim ToS)

# ---------------------------------------------------------------------------
# GraphQL query — fetch everything useful for NLP + geo
# ---------------------------------------------------------------------------

QUERY = """
query EventsSearch($criteria: SearchCriteriaInput!) {
  events(input: $criteria) {
    total page per
    results {
      id title genre startingDate endingDate datesDisplay
      hasVariousStartingTime duration boxOfficeRef
      accessibility accessibilityNotes cmsRef slug
      priceType freeTicketed canceleld
      presentedBy description ageRestriction distance

      performances {
        id title dateTime estimatedEndDateTime status duration
        notes cancelled soldOut boxOfficeId ticketStatus
        concessions { code title description }
      }

      venues { title slug }
      spaces { id title venueName venueCode }
      images { url imageType }

      attributes { id key attributeTypes value eventCode }
    }
  }
}
"""

HEADERS = {
    "authorization": f"Bearer {TOKEN}",
    "content-type": "application/json",
    "accept": "application/json",
}

# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


def fetch_page(page: int) -> dict:
    payload = {
        "query": QUERY,
        "variables": {
            "criteria": {
                "page": page,
                "per": PER_PAGE,
                "sortBy": "TITLE",
                "sortBySeed": "123",
                "recentlyAdded": "ANY",
            }
        },
        "operationName": "EventsSearch",
    }
    for attempt in range(3):
        try:
            r = requests.post(ENDPOINT, headers=HEADERS, json=payload, timeout=20)
            r.raise_for_status()
            data = r.json()
            if "errors" in data:
                raise ValueError(f"GraphQL errors: {data['errors']}")
            return data["data"]["events"]
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  Retrying page {page} after error: {e}")
            time.sleep(2**attempt)


def fetch_all() -> list[dict]:
    print("Fetching page 0 to discover total…")
    first = fetch_page(0)
    total = first["total"]
    total_pages = (total + PER_PAGE - 1) // PER_PAGE
    print(f"  {total} shows across {total_pages} pages")

    all_shows = first["results"]

    for page in tqdm(range(1, total_pages), desc="Fetching pages"):
        data = fetch_page(page)
        all_shows.extend(data["results"])
        time.sleep(0.3)  # be polite

    print(f"Fetched {len(all_shows)} shows total")
    return all_shows


# ---------------------------------------------------------------------------
# Attribute helpers
# ---------------------------------------------------------------------------


def get_attr(attributes: list[dict], key: str) -> str:
    for a in attributes:
        if a.get("key") == key:
            return a.get("value", "")
    return ""


def extract_price_range(attributes: list[dict]) -> tuple[float | None, float | None]:
    """Pull numeric price range from the explicit_material attribute string."""
    raw = get_attr(attributes, "explicit_material")
    prices = re.findall(r"£(\d+(?:\.\d+)?)", raw)
    if prices:
        floats = [float(p) for p in prices]
        return min(floats), max(floats)
    return None, None


def is_pwyw(attributes: list[dict]) -> bool:
    raw = get_attr(attributes, "explicit_material").lower()
    return "pay what you can" in raw


def content_warnings(attributes: list[dict]) -> str:
    """Comma-separated list of content warnings."""
    raw = get_attr(attributes, "explicit_material")
    # Strip the price/ticketing sentence, keep the warnings part
    warnings = (
        re.sub(r"Pay [Ww]hat [Yy]ou [Cc]an.*", "", raw).strip().rstrip(",").strip()
    )
    return warnings


def social_links(attributes: list[dict]) -> dict[str, str]:
    social_keys = {"instagram", "twitter", "facebook", "tiktok", "youtube", "website"}
    return {a["key"]: a["value"] for a in attributes if a.get("key") in social_keys}


# ---------------------------------------------------------------------------
# Flatten show → dict
# ---------------------------------------------------------------------------

AGE_ORDER = {
    "FIVE": 5,
    "EIGHT": 8,
    "TEN": 10,
    "TWELVE": 12,
    "FOURTEEN": 14,
    "SIXTEEN": 16,
    "EIGHTEEN": 18,
    "TWENTYONE": 21,
}


def flatten_show(s: dict) -> dict:
    attrs = s.get("attributes", [])
    price_min, price_max = extract_price_range(attrs)
    socials = social_links(attrs)

    # Venue — prefer venues[], fall back to spaces[].venueName
    venue_name = ""
    venue_slug = ""
    if s.get("venues"):
        venue_name = s["venues"][0]["title"]
        venue_slug = s["venues"][0]["slug"]
    elif s.get("spaces"):
        venue_name = s["spaces"][0]["venueName"]

    space_name = s["spaces"][0]["title"] if s.get("spaces") else ""
    venue_code = s["spaces"][0]["venueCode"] if s.get("spaces") else ""

    # Performances summary
    perfs = s.get("performances", [])
    perf_count = len(perfs)
    cancelled_count = sum(1 for p in perfs if p.get("cancelled"))
    sold_out_count = sum(1 for p in perfs if p.get("soldOut"))
    first_perf = perfs[0]["dateTime"] if perfs else None
    last_perf = perfs[-1]["dateTime"] if perfs else None

    # Price classification
    is_free = bool(s.get("freeTicketed")) or "FREE" in (s.get("priceType") or [])
    pwyw = is_pwyw(attrs)
    has_twoforone = "TWO_FOR_ONE" in (s.get("priceType") or [])
    has_preview = "PREVIEW" in (s.get("priceType") or [])

    # Accessibility
    accessibility = s.get("accessibility", [])

    # Age
    age_code = s.get("ageRestriction", "")
    age_numeric = AGE_ORDER.get(age_code, None)

    # Image
    images = s.get("images", [])
    thumb = next((i["url"] for i in images if i.get("imageType") == "Small"), "")

    return {
        # Identifiers
        "id": s["id"],
        "cms_ref": s.get("cmsRef", ""),
        "box_office_ref": s.get("boxOfficeRef", ""),
        "slug": s.get("slug", ""),
        # Core content (for NLP)
        "title": s.get("title", ""),
        "genre": s.get("genre", ""),
        "presented_by": s.get("presentedBy", "").strip(),
        "description": s.get("description", ""),
        "age_restriction": age_code,
        "age_numeric": age_numeric,
        "content_warnings": content_warnings(attrs),
        "cancelled": bool(s.get("canceleld")),
        # Schedule
        "dates_display": s.get("datesDisplay", ""),
        "starting_date": s.get("startingDate", ""),
        "ending_date": s.get("endingDate", ""),
        "duration_mins": s.get("duration"),
        "has_various_times": bool(s.get("hasVariousStartingTime")),
        "performance_count": perf_count,
        "cancelled_count": cancelled_count,
        "sold_out_count": sold_out_count,
        "first_performance": first_perf,
        "last_performance": last_perf,
        # Pricing
        "is_free": is_free,
        "is_pwyw": pwyw,
        "has_two_for_one": has_twoforone,
        "has_preview": has_preview,
        "price_min_gbp": price_min,
        "price_max_gbp": price_max,
        "price_types": "|".join(s.get("priceType") or []),
        # Location (for geocoding)
        "venue_name": venue_name,
        "venue_slug": venue_slug,
        "space_name": space_name,
        "venue_code": venue_code,
        # Accessibility
        "wheelchair_access": "WHEELCHAIR_ACCESS" in accessibility,
        "wheelchair_toilets": "WHEELCHAIR_ACCESSIBLE_TOILETS" in accessibility,
        "audio_enhancement": "AUDIO_ENHANCEMENT_SYSTEM" in accessibility,
        "bsl_interpreted": "BSL_INTERPRETED" in accessibility,
        "captioned": "CAPTIONED" in accessibility,
        # Social
        "url_instagram": socials.get("instagram", ""),
        "url_website": socials.get("website", ""),
        "url_twitter": socials.get("twitter", ""),
        "url_tiktok": socials.get("tiktok", ""),
        "thumbnail_url": thumb,
    }


def flatten_performance(
    perf: dict, show_id: int, show_title: str, venue_name: str
) -> dict:
    return {
        "perf_id": perf["id"],
        "show_id": show_id,
        "show_title": show_title,
        "venue_name": venue_name,
        "datetime": perf.get("dateTime"),
        "end_datetime": perf.get("estimatedEndDateTime"),
        "duration_mins": perf.get("duration"),
        "status": perf.get("status"),
        "ticket_status": perf.get("ticketStatus"),
        "cancelled": bool(perf.get("cancelled")),
        "sold_out": bool(perf.get("soldOut")),
        "box_office_id": perf.get("boxOfficeId"),
        "concessions": "|".join(c["title"] for c in perf.get("concessions", [])),
    }


# ---------------------------------------------------------------------------
# Geocode venues
# ---------------------------------------------------------------------------

# Known Edinburgh Fringe venue coordinates (saves geocoding API calls for
# the most common venues — extend this dict as needed).
KNOWN_COORDS: dict[str, tuple[float, float]] = {
    "Assembly Rooms": (55.9527, -3.1919),
    "Assembly George Square Studios": (55.9437, -3.1897),
    "Assembly George Square Theatre": (55.9437, -3.1897),
    "Gilded Balloon Teviot": (55.9448, -3.1895),
    "Gilded Balloon Patter House": (55.9451, -3.1925),
    "Pleasance Courtyard": (55.9476, -3.1844),
    "Pleasance Dome": (55.9489, -3.1756),
    "Underbelly Bristo Square": (55.9453, -3.1889),
    "Underbelly Cowgate": (55.9473, -3.1900),
    "Traverse Theatre": (55.9456, -3.2003),
    "Edinburgh Playhouse": (55.9557, -3.1817),
    "Summerhall": (55.9406, -3.1847),
    "theSpace @ Surgeons' Hall": (55.9471, -3.1852),
    "theSpace @ Symposium Hall": (55.9448, -3.1868),
    "Greenside @ George Street": (55.9522, -3.1958),
    "Greenside @ Riddles Court": (55.9495, -3.1969),
    "Laughing Horse @ The Hanover Tap": (55.9528, -3.1953),
    "Laughing Horse @ The Counting House": (55.9484, -3.1918),
    "Laughing Horse @ The Three Sisters": (55.9473, -3.1887),
    "Laughing Horse @ City Cafe": (55.9479, -3.1872),
    "Laughing Horse @ Bar 50": (55.9482, -3.1905),
    "Laughing Horse @ West Nic Records": (55.9470, -3.1938),
    "Laughing Horse @ Kick Ass Cowgate": (55.9471, -3.1897),
    "Laughing Horse @ Dropkick Murphys": (55.9468, -3.1896),
    "PBH's Free Fringe @ Voodoo Rooms": (55.9527, -3.1942),
    "PBH's Free Fringe @ Canons' Gait": (55.9502, -3.1799),
    "Just The Tonic at The Caves": (55.9483, -3.1883),
    "Just The Tonic at The Mash House": (55.9479, -3.1896),
    "Just The Tonic at The Hive": (55.9469, -3.1906),
    "Just The Tonic Nucleus": (55.9491, -3.1884),
    "Scottish Comedy Festival @ The Beehive Inn": (55.9469, -3.1930),
    "Hoots @ The Apex": (55.9449, -3.2002),
    "Hoots @ Nicolson Square": (55.9459, -3.1874),
    "Hoots @ Hilton (Bread Street)": (55.9459, -3.2022),
    "Alchemist Cocktail Bar and Restaurant": (55.9531, -3.1932),
    "ZOO Southside": (55.9412, -3.1850),
    "ZOO Playground": (55.9437, -3.1864),
    "C Theatre": (55.9459, -3.1892),
    "C venues": (55.9459, -3.1892),
    "Fringe Central": (55.9476, -3.1905),
}


def geocode_venues(
    venue_names: list[str],
) -> dict[str, tuple[float | None, float | None]]:
    """Return {venue_name: (lat, lng)} using known coords then Nominatim fallback."""
    results: dict[str, tuple[float | None, float | None]] = {}

    to_geocode = []
    for name in venue_names:
        if name in KNOWN_COORDS:
            results[name] = KNOWN_COORDS[name]
        else:
            to_geocode.append(name)

    if to_geocode:
        print(f"\nGeocoding {len(to_geocode)} unknown venues via Nominatim…")
        geolocator = Nominatim(user_agent="fringe_pipeline_2026")
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=GEOCODE_DELAY)

        for name in tqdm(to_geocode, desc="Geocoding"):
            # Try venue name + Edinburgh, then just Edinburgh postcode area
            query = f"{name}, Edinburgh, Scotland"
            try:
                loc = geocode(query)
                if loc:
                    results[name] = (loc.latitude, loc.longitude)
                else:
                    # Fallback: Edinburgh city centre
                    results[name] = (55.9533, -3.1883)
                    print(f"  Could not geocode '{name}', using city centre fallback")
            except Exception as e:
                results[name] = (None, None)
                print(f"  Geocoding error for '{name}': {e}")
    else:
        print("All venues matched from known coordinates.")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Fetch raw data
    raw_path = OUTPUT_DIR / "fringe_shows_raw.json"
    if raw_path.exists():
        print(f"Loading cached raw data from {raw_path}")
        shows = json.loads(raw_path.read_text())
    else:
        shows = fetch_all()
        raw_path.write_text(json.dumps(shows, indent=2))
        print(f"Saved raw JSON → {raw_path}")

    # 2. Flatten shows
    print("\nFlattening shows…")
    flat_shows = [flatten_show(s) for s in shows]
    shows_df = pd.DataFrame(flat_shows)

    # 3. Flatten performances
    print("Flattening performances…")
    perf_rows = []
    for s in shows:
        venue = (
            s["venues"][0]["title"]
            if s.get("venues")
            else (s["spaces"][0]["venueName"] if s.get("spaces") else "")
        )
        for p in s.get("performances", []):
            perf_rows.append(flatten_performance(p, s["id"], s["title"], venue))
    perfs_df = pd.DataFrame(perf_rows)

    # 4. Geocode venues
    unique_venues = [v for v in shows_df["venue_name"].unique() if v]
    coords = geocode_venues(unique_venues)

    venues_df = pd.DataFrame(
        [
            {"venue_name": name, "lat": lat, "lng": lng}
            for name, (lat, lng) in coords.items()
        ]
    )

    # 5. Join coordinates onto shows
    shows_df = shows_df.merge(venues_df, on="venue_name", how="left")

    # 6. Save CSVs
    shows_csv = OUTPUT_DIR / "fringe_shows.csv"
    perfs_csv = OUTPUT_DIR / "fringe_performances.csv"
    venues_csv = OUTPUT_DIR / "fringe_venues.csv"

    shows_df.to_csv(shows_csv, index=False)
    perfs_df.to_csv(perfs_csv, index=False)
    venues_df.to_csv(venues_csv, index=False)
    print(
        f"\nSaved:\n  {shows_csv}  ({len(shows_df)} shows)\n  {perfs_csv}  ({len(perfs_df)} performances)\n  {venues_csv}  ({len(venues_df)} venues)"
    )

    # 7. Save GeoJSON for mapping
    geojson = {"type": "FeatureCollection", "features": []}
    for _, row in shows_df.iterrows():
        if pd.isna(row.get("lat")):
            continue
        geojson["features"].append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row["lng"], row["lat"]]},
                "properties": {
                    k: (None if pd.isna(v) else v)
                    for k, v in row.items()
                    if k not in ("lat", "lng", "description")  # description is long
                },
            }
        )

    geojson_path = OUTPUT_DIR / "fringe_shows.geojson"
    geojson_path.write_text(json.dumps(geojson))
    print(f"  {geojson_path}  ({len(geojson['features'])} features)")

    # 8. Quick summary
    print("\n--- Dataset summary ---")
    print(f"  Shows:        {len(shows_df):,}")
    print(f"  Genres:       {shows_df['genre'].nunique()} unique")
    print(f"  Venues:       {shows_df['venue_name'].nunique()} unique")
    print(f"  Free shows:   {shows_df['is_free'].sum():,}")
    print(f"  PWYW shows:   {shows_df['is_pwyw'].sum():,}")
    print(f"  Performances: {len(perfs_df):,}")
    print("\nColumn reference:")
    for col in shows_df.columns:
        dtype = shows_df[col].dtype
        nulls = shows_df[col].isna().sum()
        print(f"  {col:<30} {str(dtype):<12} {nulls} nulls")


if __name__ == "__main__":
    main()
