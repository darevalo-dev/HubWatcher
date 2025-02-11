import json
import os
import hashlib

def generate_edreams_itinerary_id(itinerary, segments):
    """
    Generate a unique itinerary ID based on:
    "#segments-#diffcarriers-sourceStationId-segmentXdepartureLocalTime-segmentXdestinationStationId-segmentXcarrierCode-segmentXflightcodearrivalLocalTime"
    """
    segment_count = len(segments)
    carriers = {seg["carrierCode"] for seg in segments}
    carrier_count = len(carriers)

    segment_details = [
        #f"{seg['sourceStationId']}-{seg['departureLocalTime']}-{seg['destinationStationId']}-{seg['carrierCode']}-{seg['flightCode']}-{seg['arrivalLocalTime']}"
        f"-{seg['carrierCode']}-{seg['flightCode']}"
        for seg in segments
    ]

    raw_id = f"s{segment_count}-c{carrier_count}" + "".join(segment_details)
    itinerary_id = raw_id#hashlib.md5(raw_id.encode()).hexdigest()[:16]  # Hash for compact ID

    return itinerary_id

def simplify_edreams_json(input_filepath, output_filepath):
    # Load original eDreams JSON
    with open(input_filepath, "r", encoding="utf-8") as file:
        edreams_data = json.load(file)

    # Extract itineraries
    itineraries = edreams_data.get("itinerarySearchResults", {}).get("itineraryResults", [])
    segments_map = edreams_data.get("itinerarySearchResults", {}).get("segments", {})

    simplified_itineraries = []

    for itinerary in itineraries:
        segments = []

        # Extract all segment keys
        all_segment_keys = (
            itinerary.get("firstSegmentsKeys", []) +
            itinerary.get("secondSegmentsKeys", []) +
            itinerary.get("thirdSegmentsKeys", []) +
            itinerary.get("fourthSegmentsKeys", [])
        )

        # Process segments
        for segment_key in all_segment_keys:
            for segment_part in segment_key.split(","):
                if segment_part == '0':
                    continue
                flight_code = segment_part[2:]
                carrier_code = segment_part[:2]

                # Find segment in segment map
                segment = segments_map.get(segment_key, {})
                source_station = segment.get("departureStationCode", "")
                destination_station = segment.get("arrivalStationCode", "")
                departure_time = segment.get("departureDateTime", "")
                arrival_time = segment.get("arrivalDateTime", "")

                segments.append({
                    "sourceStationId": source_station,
                    "destinationStationId": destination_station,
                    "departureLocalTime": departure_time,
                    "arrivalLocalTime": arrival_time,
                    "flightCode": flight_code,
                    "carrierCode": carrier_code
                })

        itinerary_id = generate_edreams_itinerary_id(itinerary, segments)

        # Extract price details
        price_details = itinerary.get("price", {}).get("sortPrice", 0.0)

        simplified_itinerary = {
            "id": itinerary_id,
            "price": price_details,
            "currency": "EUR",
            "outbound": [],
            "inbound": []
        }

        # Split segments into outbound and inbound based on original grouping
        outbound_keys = itinerary.get("firstSegmentsKeys", [])
        inbound_keys = itinerary.get("secondSegmentsKeys", [])

        for seg in segments:
            key_repr = f"0,{seg['carrierCode']}{seg['flightCode']}"  # Reconstruct key format
            if key_repr in outbound_keys:
                simplified_itinerary["outbound"].append(seg)
            elif key_repr in inbound_keys:
                simplified_itinerary["inbound"].append(seg)

        simplified_itineraries.append(simplified_itinerary)

    # Save simplified JSON
    with open(output_filepath, "w", encoding="utf-8") as file:
        json.dump(simplified_itineraries, file, indent=4, ensure_ascii=False)

    print(f"Simplified JSON saved to {output_filepath}")

# Define paths
input_file = "edreams-response.json"
output_file = "edreams-simplified.json"

# Run script
simplify_edreams_json(input_file, output_file)