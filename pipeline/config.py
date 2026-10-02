"""Tunable constants shared by every pipeline stage (mirrored in app/app.js)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "app" / "data"

YEAR = 2026
PUJA_DAYS = [
    {"id": "mahalaya", "name": "Mahalaya", "date": "2026-10-10", "factor": 0.35},
    {"id": "panchami", "name": "Panchami", "date": "2026-10-16", "factor": 0.6},
    {"id": "shashthi", "name": "Shashthi", "date": "2026-10-17", "factor": 0.8},
    {"id": "saptami", "name": "Saptami", "date": "2026-10-18", "factor": 1.0},
    {"id": "ashtami", "name": "Ashtami", "date": "2026-10-19", "factor": 1.1},
    {"id": "navami", "name": "Navami", "date": "2026-10-20", "factor": 1.0},
    {"id": "dashami", "name": "Dashami", "date": "2026-10-21", "factor": 0.55},
]

# Relative crowd by hour of day (0..23). Early morning is quiet, and the peak is 8 pm to midnight.
HOUR_FACTORS = [
    0.85, 0.75, 0.6, 0.45, 0.3, 0.2, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45,
    0.5, 0.5, 0.55, 0.6, 0.7, 0.8, 0.9, 1.0, 1.0, 1.0, 0.95, 0.9,
]

SLOTS = {
    "early_morning": {"label": "5–9 am", "hours": [5, 6, 7, 8]},
    "morning": {"label": "9 am–12 pm", "hours": [9, 10, 11]},
    "afternoon": {"label": "12–5 pm", "hours": [12, 13, 14, 15, 16]},
    "evening": {"label": "5–9 pm", "hours": [17, 18, 19, 20]},
    "night": {"label": "9 pm–1 am", "hours": [21, 22, 23, 0]},
    "late_night": {"label": "1–5 am", "hours": [1, 2, 3, 4]},
}

# Kolkata metro-area bounding box, used for sanity-checking coordinates.
BBOX = {"lat_min": 22.40, "lat_max": 22.70, "lng_min": 88.25, "lng_max": 88.50}

# Walking model
DETOUR_FACTOR = 1.3        # straight-line → real lane distance
WALK_KMH_CROWD = 3.2       # festival crowd pace
WALK_KMH_BRISK = 4.8
NEARBY_FOOD_M = 800
NEARBY_PARKING_M = 2000
CHECKIN_RADIUS_M = 80

# Fitness model
DEFAULT_HEIGHT_CM = 165
DEFAULT_WEIGHT_KG = 65
STRIDE_FACTOR = 0.415      # stride ≈ 0.415 × height
MET_STROLL = 3.0
MET_BRISK = 3.8
QUEUE_MET = 1.5            # standing in a queue still burns something

CURATED_ITINERARIES = [
    {
        "id": "north_heritage",
        "name": "North Kolkata Heritage Trail",
        "zones": ["north"],
        "min_popularity": 1,
        "start": "sovabazar",
        "suggested_day": "ashtami",
        "suggested_start": "07:00",
        "blurb": "Kumartuli, Bagbazar, the bonedi bari and Hatibagan, finishing with kabiraji at Mitra Cafe.",
    },
    {
        "id": "central_blockbusters",
        "name": "Central Blockbusters at Dawn",
        "zones": ["central"],
        "min_popularity": 4,
        "start": "girish_park",
        "suggested_day": "saptami",
        "suggested_start": "05:30",
        "blurb": "Md. Ali Park and Santosh Mitra Square before the queues wake up, then kochuri at Putiram.",
    },
    {
        "id": "south_classic",
        "name": "South Heavyweights",
        "zones": ["south_lakemarket", "south_gariahat"],
        "min_popularity": 4,
        "start": "kalighat",
        "suggested_day": "navami",
        "suggested_start": "14:00",
        "blurb": "Chetla, Tridhara, 66 Pally and Maddox, then over to Ekdalia and Singhi Park. Phuchka on the way.",
    },
    {
        "id": "behala_trail",
        "name": "Behala & New Alipore Theme Trail",
        "zones": ["southwest"],
        "min_popularity": 1,
        "start": "tollygunge",
        "suggested_day": "shashthi",
        "suggested_start": "15:00",
        "blurb": "Suruchi's state-art theme, then the Behala theme strip by the Purple Line.",
    },
    {
        "id": "east_hop",
        "name": "Salt Lake + Lake Town Hop",
        "zones": ["salt_lake", "lake_town_dumdum"],
        "min_popularity": 3,
        "start": "city_centre",
        "suggested_day": "panchami",
        "suggested_start": "16:00",
        "blurb": "Family-friendly blocks, then the Sreebhumi spectacle once the evening rush thins.",
    },
    {
        "id": "all_nighter",
        "name": "The All-Nighter: North → South",
        "zones": ["north", "central", "south_lakemarket"],
        "min_popularity": 5,
        "start": "shyambazar",
        "suggested_day": "ashtami",
        "suggested_start": "22:00",
        "blurb": "Only the five-star pandals. Ride the Blue Line between clusters and walk till dawn.",
    },
]
