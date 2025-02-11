import os
import json
import re
import glob
import numpy as np
import matplotlib.pyplot as plt
import csv
import brotli
import hashlib
from seleniumwire import webdriver  # selenium-wire extends Selenium
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
from concurrent.futures import ThreadPoolExecutor, as_completed
from tabulate import tabulate  # install via: pip install tabulate


# -----------------------------
# Shared Functions (for Mapper and Analysis)
# -----------------------------
def extract_segments_and_carriers(itinerary_id):
    """
    Assumes itinerary_id is a string starting with "s{num}-c{num}".
    For example, "s3-c1-KL-3390-KL-6149-KL-6126" indicates 3 sections and 1 carrier.
    """
    match = re.match(r's(\d+)-c(\d+)', itinerary_id)
    if match:
        sections = int(match.group(1))
        carriers = int(match.group(2))
        return sections, carriers
    else:
        return None, None

def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


# -----------------------------
# Mapper Functions (Simplify eDO JSON)
# -----------------------------
def process_segments(segment_ids, segment_map, section_map, location_map):
    processed = []
    for seg_id in segment_ids:
        seg_obj = segment_map.get(seg_id)
        if not seg_obj:
            continue
        section_ids = seg_obj.get("segment", {}).get("sections", [])
        if not section_ids:
            continue
        for section_id in section_ids:
            sec_obj = section_map.get(section_id, {})
            sec = sec_obj.get("section", {})
            departure_geo = sec.get("from")
            arrival_geo = sec.get("to")
            departure_time = sec.get("departureDate", "")
            arrival_time = sec.get("arrivalDate", "")
            flight_code = sec.get("flightCode", "")
            carrier_code = flight_code[:2] if flight_code else ""
            if not carrier_code and seg_obj.get("segment", {}).get("carrier"):
                carrier_code = str(seg_obj["segment"]["carrier"])
            departure_iata = location_map.get(departure_geo, "")
            arrival_iata = location_map.get(arrival_geo, "")
            processed.append({
                "sourceStationId": departure_iata,
                "destinationStationId": arrival_iata,
                "departureLocalTime": departure_time,
                "arrivalLocalTime": arrival_time,
                "flightCode": flight_code,
                "carrierCode": carrier_code
            })
    return processed

def generate_edreams_itinerary_id(itinerary, segments, section_count):
    carriers = {seg["carrierCode"] for seg in segments}
    carrier_count = len(carriers)
    # Remove duplicate carrier prefix: assume flightCode already includes carrier so we remove its first two characters.
    segment_details = [f"-{seg['carrierCode']}-{seg['flightCode'][2:]}" for seg in segments]
    raw_id = f"s{section_count}-c{carrier_count}" + "".join(segment_details)
    itinerary_id = raw_id
    return itinerary_id

def simplify_edreams_json(input_filepath, output_filepath):
    data = load_json(input_filepath)
    search_results = data.get("itinerarySearchResults", {})
    itineraries = search_results.get("itineraryResults", [])
    legend = search_results.get("legend", {})
    segment_results = legend.get("segmentResults", [])
    section_results = legend.get("sectionResults", [])
    locations = legend.get("locations", [])

    segment_map = {seg["id"]: seg for seg in segment_results}
    section_map = {sec["id"]: sec for sec in section_results}
    location_map = {loc["geoNodeId"]: loc["iataCode"] for loc in locations}

    simplified_itineraries = []

    for itinerary in itineraries:
        outbound_ids = itinerary.get("firstSegments", [])
        inbound_ids = itinerary.get("secondSegments", [])
        raw_segment_ids = outbound_ids + inbound_ids

        section_count = 0
        for seg_id in raw_segment_ids:
            seg_obj = segment_map.get(seg_id)
            if seg_obj:
                sections = seg_obj.get("segment", {}).get("sections", [])
                section_count += len(sections)

        outbound_segments = process_segments(outbound_ids, segment_map, section_map, location_map)
        inbound_segments = process_segments(inbound_ids, segment_map, section_map, location_map)

        all_segments = outbound_segments + inbound_segments
        itinerary_id = generate_edreams_itinerary_id(itinerary, all_segments, section_count)

        price_details = itinerary.get("price", {}).get("sortPrice", 0.0)
        # Compute price = sortPrice + membershipPerks.fee
        membershipPerks = itinerary.get("membershipPerks", {})
        membership_fee = membershipPerks.get("fee", 0.0)
        prime_price = float(price_details) + float(membership_fee)

        simplified_itinerary = {
            "id": itinerary_id,
            "price": price_details,
            "price": prime_price,
            "currency": search_results.get("priceCurrency", "EUR"),
            "outbound": outbound_segments,
            "inbound": inbound_segments
        }
        simplified_itineraries.append(simplified_itinerary)

    with open(output_filepath, "w", encoding="utf-8") as file:
        json.dump(simplified_itineraries, file, indent=4, ensure_ascii=False)

    print(f"Simplified JSON saved to {output_filepath}")

# Define mapper file paths.
input_file = "edreams-response.json"
output_file = "edreams-simplified.json"
simplify_edreams_json(input_file, output_file)


# -----------------------------
# Helper Functions for Hub Distribution
# -----------------------------
def compute_hub_count(itin):
    """
    Compute the hub count for an itinerary.
    We assume: number of hubs = (number of sections in a leg) - 1.
    We take the maximum of the outbound and inbound hub counts.
    """
    outbound = itin.get("outbound", [])
    inbound = itin.get("inbound", [])
    hubs_outbound = len(outbound) - 1 if len(outbound) > 0 else 0
    hubs_inbound = len(inbound) - 1 if len(inbound) > 0 else 0
    return max(hubs_outbound, hubs_inbound)

def hub_distribution(itineraries):
    """
    Return a dictionary mapping hub count to frequency for the given itineraries.
    """
    dist = {}
    for itin in itineraries:
        count = compute_hub_count(itin)
        dist[count] = dist.get(count, 0) + 1
    return dist

def format_distribution(dist, total):
    """
    Format the distribution dictionary as a string:
    '0: count (pct%), 1: count (pct%), ...'
    """
    return ", ".join(f"{k}: {v} ({100*v/total:.2f}%)" for k, v in sorted(dist.items()))


# -----------------------------
# Analysis Script with Hub, Missing Flights, Constructible Analysis, and Hubs Distribution
# -----------------------------
def analyze_journey(folder):
    metadata_file = os.path.join(folder, "metadata.json")
    kiwi_file = os.path.join(folder, "kiwi-simplified.json")
    edreams_file = os.path.join(folder, "edreams-simplified.json")

    metadata = load_json(metadata_file)
    kiwi_data = load_json(kiwi_file)
    edreams_data = load_json(edreams_file)

    # Deduplicate Kiwi itineraries (by ID) to avoid repeated content.
    unique_kiwi_dict = {}
    for it in kiwi_data:
        it_id = it["id"]
        it_price = float(it["price"])
        if it_id not in unique_kiwi_dict or it_price < float(
            unique_kiwi_dict[it_id]["price"]):
            unique_kiwi_dict[it_id] = it
    unique_kiwi = list(unique_kiwi_dict.values())
    total_unique_kiwi = len(unique_kiwi)
    print(total_unique_kiwi)

    kiwi_itinerary_ids = {entry["id"] for entry in unique_kiwi}
    edreams_itinerary_ids = {entry["id"] for entry in edreams_data}

    repeated_itineraries = kiwi_itinerary_ids.intersection(edreams_itinerary_ids)
    missing_in_edreams = kiwi_itinerary_ids - edreams_itinerary_ids

    # Use price for eDO comparisons.
    cheapest_edreams_price = min(float(entry["price"]) for entry in edreams_data)
    cheapest_kiwi_price = min(float(entry["price"]) for entry in kiwi_data)

    cheaper_than_edo_cheapest_itineraries = [entry["id"] for entry in kiwi_data if float(entry["price"]) < cheapest_edreams_price]
    cheaper_than_edo_cheapest_count = len(cheaper_than_edo_cheapest_itineraries)
    print(cheaper_than_edo_cheapest_count)
    percent_over_kiwi = 100 * cheaper_than_edo_cheapest_count / total_unique_kiwi if total_unique_kiwi else 0
    percent_over_edreams = 100 * cheaper_than_edo_cheapest_count / len(edreams_itinerary_ids) if edreams_itinerary_ids else 0
    cheaper_than_edo_cheapest_str = f"{cheaper_than_edo_cheapest_count} ({percent_over_kiwi:.2f}% of Kiwi, {percent_over_edreams:.2f}% of eDO)"

    eDreams_cheaper_count = 0
    kiwi_cheaper_count = 0
    price_diff_sum = 0
    eDreams_cheaper_diffs = []
    kiwi_cheaper_diffs = []
    for itinerary_id in repeated_itineraries:
        edreams_price = float(next(entry["price"] for entry in edreams_data if entry["id"] == itinerary_id))
        kiwi_price = float(next(entry["price"] for entry in unique_kiwi if entry["id"] == itinerary_id))
        price_diff = edreams_price - kiwi_price
        price_diff_sum += price_diff
        if edreams_price < kiwi_price:
            eDreams_cheaper_count += 1
            eDreams_cheaper_diffs.append(kiwi_price - edreams_price)
        elif kiwi_price < edreams_price:
            kiwi_cheaper_count += 1
            kiwi_cheaper_diffs.append(edreams_price - kiwi_price)
    total_repeated = len(repeated_itineraries)
    percent_eDreams_cheaper_repeated = (100 * eDreams_cheaper_count / total_repeated) if total_repeated else 0
    percent_kiwi_cheaper_repeated = (100 * kiwi_cheaper_count / total_repeated) if total_repeated else 0
    overall_avg_price_diff = (price_diff_sum / total_repeated) if total_repeated else 0
    avg_diff_eDreams_cheaper = (sum(eDreams_cheaper_diffs) / len(eDreams_cheaper_diffs)) if eDreams_cheaper_diffs else 0
    avg_diff_kiwi_cheaper = (sum(kiwi_cheaper_diffs) / len(kiwi_cheaper_diffs)) if kiwi_cheaper_diffs else 0

    not_repeated_kiwi = kiwi_itinerary_ids - repeated_itineraries
    count_cheaper_non_repeated_kiwi = sum(
        1 for entry in unique_kiwi if entry["id"] in not_repeated_kiwi and float(entry["price"]) < cheapest_edreams_price
    )
    kiwi_cheaper_total = count_cheaper_non_repeated_kiwi + kiwi_cheaper_count
    total_unique_itineraries = total_unique_kiwi + len(edreams_itinerary_ids) - len(repeated_itineraries)
    percent_kiwi_cheaper_overall = 100 * kiwi_cheaper_total / total_unique_itineraries

    # ----- Hub (Location) Analysis -----
    kiwi_locations = set()
    for itin in unique_kiwi:
        for seg in itin.get("outbound", []):
            if seg.get("sourceStationId"):
                kiwi_locations.add(seg["sourceStationId"])
            if seg.get("destinationStationId"):
                kiwi_locations.add(seg["destinationStationId"])
        for seg in itin.get("inbound", []):
            if seg.get("sourceStationId"):
                kiwi_locations.add(seg["sourceStationId"])
            if seg.get("destinationStationId"):
                kiwi_locations.add(seg["destinationStationId"])
    edo_locations = set()
    for itin in edreams_data:
        for seg in itin.get("outbound", []):
            if seg.get("sourceStationId"):
                edo_locations.add(seg["sourceStationId"])
            if seg.get("destinationStationId"):
                edo_locations.add(seg["destinationStationId"])
        for seg in itin.get("inbound", []):
            if seg.get("sourceStationId"):
                edo_locations.add(seg["sourceStationId"])
            if seg.get("destinationStationId"):
                edo_locations.add(seg["destinationStationId"])
    missing_locations = kiwi_locations - edo_locations
    missing_locations_count = len(missing_locations)
    missing_locations_str = ", ".join(sorted(missing_locations))

    # Hub breakdown: For each missing hub, count usage and cheaper usage.
    hub_breakdown = []
    missing_hub_usage = {}
    missing_hub_cheaper_usage = {}
    for hub in missing_locations:
        usage = 0
        cheaper_usage = 0
        for itin in unique_kiwi:
            uses_hub = False
            for seg in itin.get("outbound", []):
                if seg.get("sourceStationId") == hub or seg.get("destinationStationId") == hub:
                    uses_hub = True
                    break
            if not uses_hub:
                for seg in itin.get("inbound", []):
                    if seg.get("sourceStationId") == hub or seg.get("destinationStationId") == hub:
                        uses_hub = True
                        break
            if uses_hub:
                usage += 1
                if itin["id"] in cheaper_than_edo_cheapest_itineraries:
                    cheaper_usage += 1
        missing_hub_usage[hub] = usage
        missing_hub_cheaper_usage[hub] = cheaper_usage
        hub_breakdown.append({
            "Hub": hub,
            "Usage": usage,
            "Cheaper Usage": cheaper_usage
        })
    missing_cheaper_hubs_count = sum(1 for hub in missing_hub_cheaper_usage if missing_hub_cheaper_usage[hub] > 0)

    # ----- New Overall "Missing Content in eDO" Calculation -----
    missing_content = len(missing_in_edreams)
    missing_content_pct = 100 * missing_content / total_unique_kiwi if total_unique_kiwi else 0
    missing_content_str = f"{missing_content} ({missing_content_pct:.2f}%)"

    repeated_percent_kiwi = 100 * total_repeated / total_unique_kiwi if total_unique_kiwi else 0
    repeated_percent_edreams = 100 * total_repeated / len(edreams_itinerary_ids) if edreams_itinerary_ids else 0
    repeated_percent_str = f"Kiwi: {repeated_percent_kiwi:.2f}%, eDO: {repeated_percent_edreams:.2f}%"

    kiwi_cheaper_repeated_str = f"{kiwi_cheaper_count} ({percent_kiwi_cheaper_repeated:.2f}%)"
    edreams_cheaper_repeated_str = f"{eDreams_cheaper_count} ({percent_eDreams_cheaper_repeated:.2f}%)"

    # ----- New Missing Hub Itinerary Count (Overall) -----
    itins_with_missing_hub = set()
    for itin in unique_kiwi:
        for seg in itin.get("outbound", []) + itin.get("inbound", []):
            if seg.get("sourceStationId") in missing_locations or seg.get("destinationStationId") in missing_locations:
                itins_with_missing_hub.add(itin["id"])
                break
    missing_hub_itinerary_count = len(itins_with_missing_hub)
    missing_hub_itinerary_pct = 100 * missing_hub_itinerary_count / total_unique_kiwi if total_unique_kiwi else 0
    missing_hub_itinerary_str = f"{missing_hub_itinerary_count} ({missing_hub_itinerary_pct:.2f}%)"

    # ----- New Missing Hub Cheaper Itinerary Count (Overall) -----
    itins_with_missing_hub_cheaper = set()
    for itin in unique_kiwi:
        for seg in itin.get("outbound", []) + itin.get("inbound", []):
            if seg.get("sourceStationId") in missing_locations or seg.get("destinationStationId") in missing_locations:
                if itin["id"] in cheaper_than_edo_cheapest_itineraries:
                    itins_with_missing_hub_cheaper.add(itin["id"])
                    break
    missing_hub_cheaper_itinerary_count = len(itins_with_missing_hub_cheaper)
    missing_hub_cheaper_itinerary_pct = 100 * missing_hub_cheaper_itinerary_count / cheaper_than_edo_cheapest_count if cheaper_than_edo_cheapest_count else 0
    missing_hub_cheaper_itinerary_str = f"{missing_hub_cheaper_itinerary_count} ({missing_hub_cheaper_itinerary_pct:.2f}%)"

    # ----- Missing Flights Analysis for Missing Itineraries -----
    kiwi_missing_flights = set()
    for itin in unique_kiwi:
        if itin["id"] in missing_in_edreams:
            for seg in itin.get("outbound", []):
                if seg.get("carrierCode") and seg.get("flightCode"):
                    kiwi_missing_flights.add(f"{seg['carrierCode']}{seg['flightCode']}")
            for seg in itin.get("inbound", []):
                if seg.get("carrierCode") and seg.get("flightCode"):
                    kiwi_missing_flights.add(f"{seg['carrierCode']}{seg['flightCode']}")
    edreams_flights = set()
    for itin in edreams_data:
        for seg in itin.get("outbound", []):
            if seg.get("carrierCode") and seg.get("flightCode"):
                edreams_flights.add(f"{seg['carrierCode']}{seg['flightCode']}")
        for seg in itin.get("inbound", []):
            if seg.get("carrierCode") and seg.get("flightCode"):
                edreams_flights.add(f"{seg['carrierCode']}{seg['flightCode']}")
    missing_flights = kiwi_missing_flights - edreams_flights
    missing_flights_str = ", ".join(sorted(missing_flights))

    # ----- Constructible Analysis for Missing Itineraries -----
    constructible_count = 0
    for itin in unique_kiwi:
        if itin["id"] in missing_in_edreams:
            kiwi_flights = set()
            for seg in itin.get("outbound", []) + itin.get("inbound", []):
                if seg.get("carrierCode") and seg.get("flightCode"):
                    kiwi_flights.add(f"{seg['carrierCode']}{seg['flightCode']}")
            if kiwi_flights and kiwi_flights.issubset(edreams_flights):
                constructible_count += 1
    constructible_pct = 100 * constructible_count / len(missing_in_edreams) if missing_in_edreams else 0
    constructible_str = f"{constructible_count} ({constructible_pct:.2f}%)"

    # ----- Constructible Analysis for Cheap Kiwi Itineraries -----
    cheap_kiwi_itins = [itin for itin in unique_kiwi if float(itin["price"]) < cheapest_edreams_price]
    constructible_cheap_count = 0
    for itin in cheap_kiwi_itins:
        kiwi_flights = set()
        for seg in itin.get("outbound", []) + itin.get("inbound", []):
            if seg.get("carrierCode") and seg.get("flightCode"):
                kiwi_flights.add(f"{seg['carrierCode']}{seg['flightCode']}")
        if kiwi_flights and kiwi_flights.issubset(edreams_flights):
            constructible_cheap_count += 1
    constructible_cheap_pct = 100 * constructible_cheap_count / len(cheap_kiwi_itins) if cheap_kiwi_itins else 0
    constructible_cheap_str = f"{constructible_cheap_count} ({constructible_cheap_pct:.2f}%)"

    # ----- New Analysis: Cheap Kiwi Itineraries with FR Flights (Overall) -----
    cheap_kiwi_with_FR_count = 0
    for itin in cheap_kiwi_itins:
        if any(seg.get("carrierCode") == "FR" for seg in (itin.get("outbound", []) + itin.get("inbound", []))):
            cheap_kiwi_with_FR_count += 1
    cheap_kiwi_total = len(cheap_kiwi_itins)
    cheap_kiwi_with_FR_pct = 100 * cheap_kiwi_with_FR_count / cheap_kiwi_total if cheap_kiwi_total else 0

    # ----- New Analysis: Cheap Missing NonHub with FR Flights -----
    # Among the cheap missing itineraries that are NOT missing due to hub issues:
    cheap_missing = [itin for itin in cheap_kiwi_itins if itin["id"] in missing_in_edreams]
    cheap_missing_hub = [itin for itin in cheap_missing if any(
        seg.get("sourceStationId") in missing_locations or seg.get("destinationStationId") in missing_locations
        for seg in (itin.get("outbound", []) + itin.get("inbound", []))
    )]
    cheap_missing_nonhub = [itin for itin in cheap_missing if itin not in cheap_missing_hub]
    cheap_missing_nonhub_count = len(cheap_missing_nonhub)
    cheap_missing_nonhub_with_FR_count = 0
    for itin in cheap_missing_nonhub:
        if any(seg.get("carrierCode") == "FR" for seg in (itin.get("outbound", []) + itin.get("inbound", []))):
            cheap_missing_nonhub_with_FR_count += 1
    cheap_missing_nonhub_with_FR_pct = 100 * cheap_missing_nonhub_with_FR_count / cheap_missing_nonhub_count if cheap_missing_nonhub_count else 0
    cheap_missing_nonhub_with_FR_str = f"{cheap_missing_nonhub_with_FR_count} ({cheap_missing_nonhub_with_FR_pct:.2f}%)"

    # ----- Deep Analysis for Cheap Kiwi Itineraries -----
    cheap_missing_count = len(cheap_missing)
    cheap_missing_hub_count = len(cheap_missing_hub)
    cheap_missing_nonhub_count = cheap_missing_count - cheap_missing_hub_count
    cheap_kiwi_total = len(cheap_kiwi_itins)
    deep_cheap_analysis = {
         "Total Cheap Kiwi": cheap_kiwi_total,
         "Cheap Missing Count": cheap_missing_count,
         "Cheap Missing Due to Hub": cheap_missing_hub_count,
         "Cheap Missing Not Due to Hub": cheap_missing_nonhub_count,
         "Cheap Missing NonHub with FR Flights": cheap_missing_nonhub_with_FR_str,
         "Cheaper Kiwi with FR Flights": f"{cheap_kiwi_with_FR_count} ({cheap_kiwi_with_FR_pct:.2f}%)"
    }

    # ----- Missing Carrier Analysis -----
    # (We assume missing_flights is defined below.)
    missing_flights_carriers = {f[:2] for f in missing_flights}  # first two characters as carrier code.
    edreams_carriers = set()
    for itin in edreams_data:
        for seg in itin.get("outbound", []):
            if seg.get("carrierCode"):
                edreams_carriers.add(seg["carrierCode"])
        for seg in itin.get("inbound", []):
            if seg.get("carrierCode"):
                edreams_carriers.add(seg["carrierCode"])
    missing_carriers = missing_flights_carriers - edreams_carriers
    missing_carriers_str = ", ".join(sorted(missing_carriers))
    missing_carriers_count = len(missing_carriers)

    # ----- Total Unique Cities Calculation for Hub Analysis -----
    all_unique_cities = kiwi_locations.union(edo_locations)
    total_unique_cities = len(all_unique_cities)
    missing_hub_cities_pct = 100 * missing_locations_count / (total_unique_cities - 2) if total_unique_cities > 2 else 0

    # ----- NEW: Hubs Distribution Calculation (on Unique Kiwi Itineraries) -----
    unique_kiwi = list({it["id"]: it for it in kiwi_data}.values())
    total_unique_kiwi = len(unique_kiwi)
    all_hub_dist = hub_distribution(unique_kiwi)
    formatted_all_hub_dist = format_distribution(all_hub_dist, total_unique_kiwi)

    unique_cheap = list({it["id"]: it for it in kiwi_data if float(it["price"]) < cheapest_edreams_price}.values())
    total_unique_cheap = len(unique_cheap)
    cheap_hub_dist = hub_distribution(unique_cheap)
    formatted_cheap_hub_dist = format_distribution(cheap_hub_dist, total_unique_cheap)

    # Add these as new fields in the results.
    hubs_distribution_all = formatted_all_hub_dist
    hubs_distribution_cheap = formatted_cheap_hub_dist

    results = {
        "Journey": metadata.get("journey", f"{metadata.get('departure','')}-{metadata.get('arrival','')}"),
        "Departure": metadata.get("departure", ""),
        "Arrival": metadata.get("arrival", ""),
        "Total Kiwi": total_unique_kiwi,
        "Total eDreams": len(edreams_itinerary_ids),
        "Repeated": total_repeated,
        "Repeated %": repeated_percent_str,
        "Missing Content in eDO": missing_content_str,
        "Cheapest eDreams": cheapest_edreams_price,
        "Cheapest Kiwi": cheapest_kiwi_price,
        "Kiwi cheaper": kiwi_cheaper_repeated_str,
        "eDreams cheaper": edreams_cheaper_repeated_str,
        "Overall Avg Price Diff": overall_avg_price_diff,
        "Avg Diff when eDreams Cheaper": avg_diff_eDreams_cheaper,
        "Avg Diff when Kiwi Cheaper": avg_diff_kiwi_cheaper,
        "Overall % of itineraries were Kiwi was cheaper": percent_kiwi_cheaper_overall,
        "Kiwi itineraries cheaper the eDO cheapest": cheaper_than_edo_cheapest_str,
        "Missing Hub Cities in eDO": missing_locations_str,
        "Missing Hub Cities Count": f"{missing_locations_count} ({missing_hub_cities_pct:.2f}%)",
        "Missing Cheaper Hubs Count": missing_cheaper_hubs_count,
        "Missing Hub Itinerary Count": missing_hub_itinerary_str,
        "Missing Hub Cheaper Itinerary Count": missing_hub_cheaper_itinerary_str,
        "Missing Flights": missing_flights_str,
        "Constructible": constructible_str,
        "Constructible among Cheap Kiwi": constructible_cheap_str,
        "Missing Carriers": missing_carriers_str,
        "Missing Carriers Count": missing_carriers_count,
        "Cheaper Kiwi with FR Flights": f"{cheap_kiwi_with_FR_count} ({cheap_kiwi_with_FR_pct:.2f}%)",
        "Hub Breakdown": hub_breakdown,
        "Cheap Analysis": deep_cheap_analysis,
        "Hubs Distribution (All Kiwi)": hubs_distribution_all,
        "Hubs Distribution (Cheap Kiwi)": hubs_distribution_cheap
    }
    return results


# -----------------------------
# Main: Process Test Folders, Build Tables and Export Graphs
# -----------------------------
test_folders = ["test1", "test2", "test3", "test4"]

all_results = []
hub_breakdown_all = []
cheap_analysis_table = []  # New table for deep cheap analysis
hubs_distribution_table = []  # New table for hubs distribution
for folder in test_folders:
    if os.path.isdir(folder):
        result = analyze_journey(folder)
        all_results.append(result)
        for hub_info in result.get("Hub Breakdown", []):
            hub_breakdown_all.append([result["Journey"], hub_info["Hub"], hub_info["Usage"], hub_info["Cheaper Usage"]])
        ca = result.get("Cheap Analysis", {})
        cheap_analysis_table.append([
            result["Journey"],
            ca.get("Total Cheap Kiwi", ""),
            ca.get("Cheap Missing Count", ""),
            ca.get("Cheap Missing Due to Hub", ""),
            ca.get("Cheap Missing Not Due to Hub", ""),
            ca.get("Cheap Missing NonHub with FR Flights", ""),
            ca.get("Cheaper Kiwi with FR Flights", "")
        ])
        hubs_distribution_table.append([
            result["Journey"],
            result.get("Hubs Distribution (All Kiwi)", ""),
            result.get("Hubs Distribution (Cheap Kiwi)", "")
        ])
    else:
        print(f"Folder {folder} not found.")

# Define table headers.
content_headers = [
    "Journey", "Departure", "Arrival",
    "Total Kiwi", "Total eDreams",
    "Repeated", "Repeated %", "Missing Content in eDO",
    "Missing Flights", "Constructible", "Constructible among Cheap Kiwi",
    "Missing Carriers", "Missing Carriers Count",
    "Cheaper Kiwi with FR Flights"
]

global_pricing_headers = [
    "Journey",
    "Kiwi itineraries cheaper the eDO cheapest",
    "Cheapest eDreams", "Cheapest Kiwi",
    "Overall % of itineraries were Kiwi was cheaper"
]

repeated_pricing_headers = [
    "Journey",
    "Kiwi cheaper", "eDreams cheaper",
    "Overall Avg Price Diff",
    "Avg Diff when eDreams Cheaper", "Avg Diff when Kiwi Cheaper"
]

hub_data_headers = [
    "Journey",
    "Missing Hub Cities in eDO",
    "Missing Hub Cities Count",
    "Missing Cheaper Hubs Count",
    "Missing Hub Itinerary Count",
    "Missing Hub Cheaper Itinerary Count"
]

hub_breakdown_headers = ["Journey", "Hub", "Usage", "Cheaper Usage"]

cheap_analysis_headers = [
    "Journey",
    "Total Cheap Kiwi",
    "Cheap Missing Count",
    "Cheap Missing Due to Hub",
    "Cheap Missing Not Due to Hub",
    "Cheap Missing NonHub with FR Flights",
    "Cheaper Kiwi with FR Flights"
]

hubs_distribution_headers = [
    "Journey",
    "Hubs Distribution (All Kiwi)",
    "Hubs Distribution (Cheap Kiwi)"
]

# Build the tables.
content_table = [[res[h] for h in content_headers] for res in all_results]
global_pricing_table = [[res[h] for h in global_pricing_headers] for res in all_results]
repeated_pricing_table = [[res[h] for h in repeated_pricing_headers] for res in all_results]
hub_data_table = [[res["Journey"],
                   res["Missing Hub Cities in eDO"],
                   res["Missing Hub Cities Count"],
                   res["Missing Cheaper Hubs Count"],
                   res["Missing Hub Itinerary Count"],
                   res["Missing Hub Cheaper Itinerary Count"]]
                  for res in all_results]
hub_breakdown_table = []
for res in all_results:
    journey = res["Journey"]
    for hub_info in res.get("Hub Breakdown", []):
        hub_breakdown_table.append([journey, hub_info["Hub"], hub_info["Usage"], hub_info["Cheaper Usage"]])
cheap_analysis_table_final = cheap_analysis_table
hubs_distribution_table_final = hubs_distribution_table

print("\nContent Related Data:")
print(tabulate(content_table, headers=content_headers, tablefmt="grid"))
print("\nGlobal Pricing Data:")
print(tabulate(global_pricing_table, headers=global_pricing_headers, tablefmt="grid"))
print("\nRepeated Pricing Data:")
print(tabulate(repeated_pricing_table, headers=repeated_pricing_headers, tablefmt="grid"))
print("\nHigh-Level Hub Data:")
print(tabulate(hub_data_table, headers=hub_data_headers, tablefmt="grid"))
print("\nHub Breakdown Data:")
print(tabulate(hub_breakdown_table, headers=hub_breakdown_headers, tablefmt="grid"))
print("\nCheap Analysis Data:")
print(tabulate(cheap_analysis_table_final, headers=cheap_analysis_headers, tablefmt="grid"))
print("\nHubs Distribution Data:")
print(tabulate(hubs_distribution_table_final, headers=hubs_distribution_headers, tablefmt="grid"))

# Export tables to CSV.
def export_to_csv(filename, headers, table_data):
    with open(filename, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        writer.writerows(table_data)

export_to_csv("outputs/content_data.csv", content_headers, content_table)
export_to_csv("outputs/global_pricing_data.csv", global_pricing_headers, global_pricing_table)
export_to_csv("outputs/repeated_pricing_data.csv", repeated_pricing_headers, repeated_pricing_table)
export_to_csv("outputs/hub_data.csv", hub_data_headers, hub_data_table)
export_to_csv("outputs/hub_breakdown_data.csv", hub_breakdown_headers, hub_breakdown_table)
export_to_csv("outputs/cheap_analysis_data.csv", cheap_analysis_headers, cheap_analysis_table_final)
export_to_csv("outputs/hubs_distribution_data.csv", hubs_distribution_headers, hubs_distribution_table_final)

print("\nCSV files 'content_data.csv', 'global_pricing_data.csv', 'repeated_pricing_data.csv', 'hub_data.csv', 'hub_breakdown_data.csv', 'cheap_analysis_data.csv', and 'hubs_distribution_data.csv' have been saved.")

# -----------------------------
# Graph Export Functions
# -----------------------------
os.makedirs("plots", exist_ok=True)

def save_graphs(folder, kiwi_data, edreams_data):
    metadata = load_json(os.path.join(folder, "metadata.json"))
    journey = metadata.get("journey", folder)
    edreams_prices = [float(entry["price"]) for entry in edreams_data]
    kiwi_prices = [float(entry["price"]) for entry in kiwi_data]
    plt.figure(figsize=(10, 6))
    bins = 30
    plt.hist(edreams_prices, bins=bins, color='blue', alpha=0.6, label='eDO (price)')
    plt.hist(kiwi_prices, bins=bins, color='green', alpha=0.6, label='Kiwi')
    plt.xlabel('Price')
    plt.ylabel('Frequency')
    plt.title(f'Price Distribution - {journey}')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join("plots", f"{folder}_price_distribution.png"))
    plt.close()

def save_section_distribution(folder, kiwi_data, edreams_data):
    metadata = load_json(os.path.join(folder, "metadata.json"))
    journey = metadata.get("journey", folder)
    kiwi_sections = []
    edreams_sections = []
    for entry in kiwi_data:
        res = extract_segments_and_carriers(entry["id"])
        if res:
            kiwi_sections.append(res[0])
    for entry in edreams_data:
        res = extract_segments_and_carriers(entry["id"])
        if res:
            edreams_sections.append(res[0])
    plt.figure(figsize=(10,6))
    bins = range(min(kiwi_sections+edreams_sections), max(kiwi_sections+edreams_sections)+2)
    plt.hist(kiwi_sections, bins=bins, color='green', alpha=0.6, label='Kiwi')
    plt.hist(edreams_sections, bins=bins, color='blue', alpha=0.6, label='eDO')
    plt.xlabel('Number of Sections')
    plt.ylabel('Frequency')
    plt.title(f'Section Distribution - {journey}')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join("plots", f"{folder}_section_distribution.png"))
    plt.close()

def save_carrier_distribution(folder, kiwi_data, edreams_data):
    metadata = load_json(os.path.join(folder, "metadata.json"))
    journey = metadata.get("journey", folder)
    kiwi_carriers = []
    edreams_carriers = []
    for entry in kiwi_data:
        res = extract_segments_and_carriers(entry["id"])
        if res:
            kiwi_carriers.append(res[1])
    for entry in edreams_data:
        res = extract_segments_and_carriers(entry["id"])
        if res:
            edreams_carriers.append(res[1])
    plt.figure(figsize=(10,6))
    bins = range(min(kiwi_carriers+edreams_carriers), max(kiwi_carriers+edreams_carriers)+2)
    plt.hist(kiwi_carriers, bins=bins, color='green', alpha=0.6, label='Kiwi')
    plt.hist(edreams_carriers, bins=bins, color='blue', alpha=0.6, label='eDO')
    plt.xlabel('Number of Carriers')
    plt.ylabel('Frequency')
    plt.title(f'Carrier Distribution - {journey}')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join("plots", f"{folder}_carrier_distribution.png"))
    plt.close()

for folder in test_folders:
    if os.path.isdir(folder):
        kiwi_data = load_json(os.path.join(folder, "kiwi-simplified.json"))
        edreams_data = load_json(os.path.join(folder, "edreams-simplified.json"))
        save_graphs(folder, kiwi_data, edreams_data)
        save_section_distribution(folder, kiwi_data, edreams_data)
        save_carrier_distribution(folder, kiwi_data, edreams_data)