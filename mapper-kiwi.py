import json
import os
import hashlib

def generate_itinerary_id(itinerary):
    """
    Generate a unique itinerary ID based on:
    "#segments-#diffcarriers-sourceStationId-segmentXdepartureLocalTime-segmentXdestinationStationId-segmentXcarrierCode-segmentXflightcodearrivalLocalTime"
    """
    segments = []
    carriers = set()

    for sector in itinerary.get("outbound", {}).get("sectorSegments", []) + itinerary.get("inbound", {}).get("sectorSegments", []):
        segment = sector.get("segment", {})
        source = segment.get("source", {}).get("station", {}).get("code", "")
        destination = segment.get("destination", {}).get("station", {}).get("code", "")
        carrier_code = segment.get("carrier", {}).get("code", "")
        flight_code = segment.get("code", "")

        #segments.append(f"{source}-{destination}-{carrier_code}-{flight_code}")
        segments.append(f"{carrier_code}-{flight_code}")
        carriers.add(carrier_code)

    segment_count = len(segments)
    carrier_count = len(carriers)
    raw_id = f"s{segment_count}-c{carrier_count}-" + "-".join(segments)

    # Generate a hash to keep ID length manageable
    itinerary_id = raw_id#hashlib.md5(raw_id.encode()).hexdigest()[:16]

    return itinerary_id

def simplify_kiwi_json(input_filepath, output_filepath):
    # Load original Kiwi JSON
    with open(input_filepath, "r", encoding="utf-8") as file:
        kiwi_data = json.load(file)

    # Extract itineraries
    itineraries = kiwi_data.get("data", {}).get("returnItineraries", {}).get("itineraries", [])

    simplified_itineraries = []

    for itinerary in itineraries:
        itinerary_id = generate_itinerary_id(itinerary)

        simplified_itinerary = {
            "id": itinerary_id,
            "price": itinerary.get("priceEur", {}).get("amount"),
            "currency": "EUR",
            "outbound": [],
            "inbound": []
        }

        # Process outbound segments
        for sector in itinerary.get("outbound", {}).get("sectorSegments", []):
            segment = sector.get("segment", {})
            simplified_itinerary["outbound"].append({
                "sourceStationId": segment.get("source", {}).get("station", {}).get("code"),
                "destinationStationId": segment.get("destination", {}).get("station", {}).get("code"),
                "departureLocalTime": segment.get("source", {}).get("localTime"),
                "arrivalLocalTime": segment.get("destination", {}).get("localTime"),
                "flightCode": segment.get("code"),
                "carrierCode": segment.get("carrier", {}).get("code")
            })

        # Process inbound segments
        for sector in itinerary.get("inbound", {}).get("sectorSegments", []):
            segment = sector.get("segment", {})
            simplified_itinerary["inbound"].append({
                "sourceStationId": segment.get("source", {}).get("station", {}).get("code"),
                "destinationStationId": segment.get("destination", {}).get("station", {}).get("code"),
                "departureLocalTime": segment.get("source", {}).get("localTime"),
                "arrivalLocalTime": segment.get("destination", {}).get("localTime"),
                "flightCode": segment.get("code"),
                "carrierCode": segment.get("carrier", {}).get("code")
            })

        simplified_itineraries.append(simplified_itinerary)

    # Save simplified JSON
    with open(output_filepath, "w", encoding="utf-8") as file:
        json.dump(simplified_itineraries, file, indent=4, ensure_ascii=False)

    print(f"Simplified JSON saved to {output_filepath}")

# Define paths
input_file = "kiwi-response.json"
output_file = "kiwi-simplified.json"

# Run script
simplify_kiwi_json(input_file, output_file)