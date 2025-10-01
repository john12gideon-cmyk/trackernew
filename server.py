import os
import re
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError, PyMongoError
from dotenv import load_dotenv

# Load environment variables from .env (optional)
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "tracking_db")
COLLECTION_NAME = os.getenv("MONGO_COLLECTION", "users_locations")
PORT = int(os.getenv("PORT", 5000))

app = Flask(__name__)
CORS(app)

# Connect to MongoDB
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
collection = db[COLLECTION_NAME]

# Ensure unique index on phone (phone as unique identifier)
collection.create_index([("phone", ASCENDING)], unique=True)

# Basic phone validation (E.164-ish): optional +, 7-15 digits
PHONE_REGEX = re.compile(r"^\+?\d{7,15}$")

def validate_phone(phone):
    if not isinstance(phone, str):
        return False
    return bool(PHONE_REGEX.match(phone.strip()))

def validate_lat_lon(lat, lon):
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return False
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return False
    return True

@app.route("/api/location", methods=["POST"])
def update_location():
    """
    Accepts JSON body with: phone, latitude, longitude
    Example:
    {
      "phone": "+12345556789",
      "latitude": 37.4219983,
      "longitude": -122.084
    }
    """
    if not request.is_json:
        return jsonify({"error": "Request body must be JSON"}), 400

    data = request.get_json()
    phone = data.get("phone")
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    # Validate inputs
    if phone is None or latitude is None or longitude is None:
        return jsonify({"error": "Missing required fields: phone, latitude, longitude"}), 400

    if not validate_phone(phone):
        return jsonify({"error": "Invalid phone format. Use digits with optional leading '+', 7-15 digits."}), 400

    if not validate_lat_lon(latitude, longitude):
        return jsonify({"error": "Invalid latitude/longitude range or format."}), 400

    # Prepare document
    now = datetime.utcnow()
    doc = {
        "phone": phone.strip(),
        "location": {
            "latitude": float(latitude),
            "longitude": float(longitude)
        },
        "updated_at": now
    }

    try:
        # Use upsert to insert or update existing phone entry
        result = collection.update_one(
            {"phone": doc["phone"]},
            {"$set": {"location": doc["location"], "updated_at": doc["updated_at"]}},
            upsert=True
        )
    except PyMongoError as e:
        app.logger.exception("Database error while updating location")
        return jsonify({"error": "Database error", "details": str(e)}), 500

    return jsonify({
        "message": "Location stored",
        "phone": doc["phone"],
        "location": doc["location"],
        "updated_at": doc["updated_at"].isoformat() + "Z"
    }), 200

@app.route("/api/location/<phone>", methods=["GET"])
def get_latest_location(phone):
    """
    Retrieve the latest location for the given phone number.
    Phone param should match the same format used to store the phone.
    """
    if not validate_phone(phone):
        return jsonify({"error": "Invalid phone format."}), 400

    try:
        doc = collection.find_one({"phone": phone})
    except PyMongoError as e:
        app.logger.exception("Database error while fetching location")
        return jsonify({"error": "Database error", "details": str(e)}), 500

    if not doc:
        return jsonify({"error": "No location found for this phone number"}), 404

    response = {
        "phone": doc["phone"],
        "location": {
            "latitude": doc["location"]["latitude"],
            "longitude": doc["location"]["longitude"]
        },
        "updated_at": doc["updated_at"].isoformat() + "Z"
    }
    return jsonify(response), 200

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")