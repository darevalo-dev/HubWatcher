import os
import json
import re
import glob
import numpy as np
import matplotlib.pyplot as plt
import csv
import hashlib


def generate_edreams_itinerary_id(itinerary, segments, section_count):
  """
  Generate a unique itinerary ID based on:
  "s{#sections}-c{#unique carriers}" concatenated with each segment's carrier and flight code.
  'section_count' is the total number of sections.
  """
  carriers = {seg["carrierCode"] for seg in segments}
  carrier_count = len(carriers)

  # Concatenate carrier and flight codes from each processed segment.
  segment_details = [f"-{seg['carrierCode']}-{seg['flightCode']}" for seg in
                     segments]

  raw_id = f"s{section_count}-c{carrier_count}" + "".join(segment_details)
  # Optionally, to compact the ID:
  # itinerary_id = hashlib.md5(raw_id.encode()).hexdigest()[:16]
  itinerary_id = raw_id
  return itinerary_id


def load_json(file_path):
  with open(file_path, "r", encoding="utf-8") as file:
    return json.load(file)


def process_segments(segment_ids, segment_map, section_map, location_map):
  """
  Given a list of segment IDs, lookup each segment in segment_map.
  For each segment, process all section IDs in its "sections" list (inside the "segment" key).
  For each section, retrieve detailed flight info from section_map and the corresponding IATA codes via location_map.
  Returns a list of processed segment dictionaries (one per section).
  """
  processed = []
  for seg_id in segment_ids:
    seg_obj = segment_map.get(seg_id)
    if not seg_obj:
      continue
    # Retrieve the section IDs from the segment object.
    section_ids = seg_obj.get("segment", {}).get("sections", [])
    if not section_ids:
      continue
    # Process each section in the segment.
    for section_id in section_ids:
      sec_obj = section_map.get(section_id, {})
      sec = sec_obj.get("section", {})
      # Extract departure and arrival geo node IDs.
      departure_geo = sec.get("from")
      arrival_geo = sec.get("to")
      departure_time = sec.get("departureDate", "")
      arrival_time = sec.get("arrivalDate", "")
      flight_code = sec.get("flightCode", "")
      # Derive carrier code: try using first two letters of flight code or fallback to seg carrier.
      carrier_code = flight_code[:2] if flight_code else ""
      if not carrier_code and seg_obj.get("segment", {}).get("carrier"):
        carrier_code = str(seg_obj["segment"]["carrier"])
      # Lookup IATA codes via location_map.
      departure_iata = location_map.get(departure_geo, "")
      arrival_iata = location_map.get(arrival_geo, "")

      processed.append({
        "sourceStationId": departure_iata,
        "destinationStationId": arrival_iata,
        "departureLocalTime": departure_time,
        "arrivalLocalTime": arrival_time,
        "flightCode": flight_code[2:],
        "carrierCode": carrier_code
      })
  return processed


def simplify_edreams_json(input_filepath, output_filepath):
  # Load original edreams JSON.
  data = load_json(input_filepath)
  search_results = data.get("itinerarySearchResults", {})
  itineraries = search_results.get("itineraryResults", [])

  # Mapping information is inside the "legend" object.
  legend = search_results.get("legend", {})
  segment_results = legend.get("segmentResults", [])
  section_results = legend.get("sectionResults", [])
  locations = legend.get("locations", [])

  # Build mapping dictionaries.
  segment_map = {seg["id"]: seg for seg in segment_results}
  section_map = {sec["id"]: sec for sec in section_results}
  location_map = {loc["geoNodeId"]: loc["iataCode"] for loc in locations}

  simplified_itineraries = []

  for itinerary in itineraries:
    # Retrieve raw segment IDs for outbound and inbound.
    outbound_ids = itinerary.get("firstSegments", [])
    inbound_ids = itinerary.get("secondSegments", [])
    raw_segment_ids = outbound_ids + inbound_ids

    # Compute total number of sections across raw segments.
    section_count = 0
    for seg_id in raw_segment_ids:
      seg_obj = segment_map.get(seg_id)
      if seg_obj:
        sections = seg_obj.get("segment", {}).get("sections", [])
        section_count += len(sections)

    # Process outbound and inbound segments.
    outbound_segments = process_segments(outbound_ids, segment_map, section_map,
                                         location_map)
    inbound_segments = process_segments(inbound_ids, segment_map, section_map,
                                        location_map)

    # Combine processed segments for itinerary ID generation.
    all_segments = outbound_segments + inbound_segments
    itinerary_id = generate_edreams_itinerary_id(itinerary, all_segments,
                                                 section_count)

    # Extract price details (assuming itinerary["price"]["sortPrice"]).
    price_details = itinerary.get("price", {}).get("sortPrice", 0.0)

    simplified_itinerary = {
      "id": itinerary_id,
      "price": price_details,
      "currency": search_results.get("priceCurrency", "EUR"),
      "outbound": outbound_segments,
      "inbound": inbound_segments
    }
    simplified_itineraries.append(simplified_itinerary)

  # Save simplified JSON.
  with open(output_filepath, "w", encoding="utf-8") as file:
    json.dump(simplified_itineraries, file, indent=4, ensure_ascii=False)

  print(f"Simplified JSON saved to {output_filepath}")


# Define paths.
input_file = "edreams-response.json"
output_file = "edreams-simplified.json"

# Run the mapper script.
simplify_edreams_json(input_file, output_file)