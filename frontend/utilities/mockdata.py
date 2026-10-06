"""Shared mock records used by the frontend pages."""

INVENTORY_ITEMS = [
    {
        "id": 1,
        "name": "Canon EOS R6",
        "category": "Electronics",
        "location": "Office",
        "estimated_value": 1850,
        "status": "Current",
        "icon": "photo_camera",
    },
    {
        "id": 2,
        "name": "Seiko Prospex",
        "category": "Watches",
        "location": "Bedroom",
        "estimated_value": 725,
        "status": "Review",
        "icon": "watch",
    },
    {
        "id": 3,
        "name": "MacBook Pro",
        "category": "Electronics",
        "location": "Office",
        "estimated_value": 1250,
        "status": "Current",
        "icon": "laptop_mac",
    },
    {
        "id": 4,
        "name": "Lake Painting",
        "category": "Art",
        "location": "Living Room",
        "estimated_value": 475,
        "status": "Current",
        "icon": "image",
    },
    {
        "id": 5,
        "name": "Leather Couch",
        "category": "Furniture",
        "location": "Living Room",
        "estimated_value": 2100,
        "status": "Current",
        "icon": "chair",
    },
    {
        "id": 6,
        "name": "Titleist Golf Clubs",
        "category": "Sports",
        "location": "Garage",
        "estimated_value": 850,
        "status": "Review",
        "icon": "sports_golf",
    },
    {
        "id": 7,
        "name": "Vintage Record Player",
        "category": "Collectibles",
        "location": "Living Room",
        "estimated_value": 620,
        "status": "Current",
        "icon": "album",
    },
    {
        "id": 8,
        "name": "Hiking Backpack",
        "category": "Outdoor",
        "location": "Garage",
        "estimated_value": 220,
        "status": "Current",
        "icon": "backpack",
    },
]

_VALUATION_DETAILS = {
    1: {
        "current_value": 1850,
        "last_updated": "1 day ago",
        "days_old": 1,
        "status": "Needs Review",
    },
    2: {
        "current_value": 725,
        "last_updated": "9 days ago",
        "days_old": 9,
        "status": "Current",
    },
    3: {
        "current_value": 1290,
        "last_updated": "14 days ago",
        "days_old": 14,
        "status": "Current",
    },
    6: {
        "current_value": 850,
        "last_updated": "72 days ago",
        "days_old": 72,
        "status": "Needs Review",
    },
    7: {
        "current_value": 520,
        "last_updated": "105 days ago",
        "days_old": 105,
        "status": "Needs Review",
    },
    5: {
        "current_value": 2100,
        "last_updated": "88 days ago",
        "days_old": 88,
        "status": "Needs Review",
    },
}

_INVENTORY_ITEMS_BY_ID = {item["id"]: item for item in INVENTORY_ITEMS}
VALUATION_ITEMS = [
    {**_INVENTORY_ITEMS_BY_ID[item_id], **details}
    for item_id, details in _VALUATION_DETAILS.items()
]

AI_PREVIEW = {
    "name": "Canon EOS R6",
    "current_estimate": 1850,
    "range_low": 1700,
    "range_high": 2000,
    "confidence": "High",
    "sources": [
        {"name": "B&H Photo", "value": 1899},
        {"name": "Amazon", "value": 1750},
        {"name": "KEH Camera", "value": 1850},
        {"name": "MPB", "value": 1795},
    ],
}
