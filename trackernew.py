from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(_name_)

# In-memory store (use a database for production)
location_data = {}

@app.route('/update-location', methods=['POST'])
def update_location():
    data = request.get_json()
    phone = data.get('phone_number')
    lat = data.get('latitude')
    lon = data.get('longitude')
    timestamp = data.get('timestamp', datetime.utcnow().isoformat())

    if not phone or lat is None or lon is None:
        return jsonify({"error": "Missing data"}), 400

    location_data[phone] = {
        "latitude": lat,
        "longitude": lon,
        "timestamp": timestamp
    }

    print(f"Updated location for {phone}: {lat}, {lon} at {timestamp}")
    return jsonify({"status": "success"}), 200

@app.route('/get-location/<phone>', methods=['GET'])
def get_location(phone):
    data = location_data.get(phone)
    if not data:
        return jsonify({"error": "No data for this phone"}), 404
    return jsonify(data), 200

if _name_ == '_main_':
    app.run(host='0.0.0.0', port=5000)