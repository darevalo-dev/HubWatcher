import json
import matplotlib.pyplot as plt
import re
import numpy as np

# Helper function to extract segments and carriers from the composed id.
def extract_segments_and_carriers(itinerary_id):
    """
    Assumes itinerary_id is a string starting with "s{num}-c{num}".
    For example, "s3-c1-KL-3390-KL-6149-KL-6126" indicates 3 segments and 1 carrier.
    """
    # Use regex to extract the number after 's' and 'c'
    match = re.match(r's(\d+)-c(\d+)', itinerary_id)
    if match:
        segments = int(match.group(1))
        carriers = int(match.group(2))
        return segments, carriers
    else:
        return None, None

# Load JSON files
def load_json(file_path):
    with open(file_path, "r") as file:
        return json.load(file)

# File paths
kiwi_file_path = "kiwi-simplified.json"
edreams_file_path = "edreams-simplified.json"

# Load data
kiwi_data = load_json(kiwi_file_path)
edreams_data = load_json(edreams_file_path)

# Create sets for itinerary ids
kiwi_itinerary_ids = {entry["id"] for entry in kiwi_data}
edreams_itinerary_ids = {entry["id"] for entry in edreams_data}

# Find repeated itineraries
repeated_itineraries = kiwi_itinerary_ids.intersection(edreams_itinerary_ids)

# Find missing itineraries
missing_in_edreams = kiwi_itinerary_ids - edreams_itinerary_ids
missing_in_kiwi = edreams_itinerary_ids - kiwi_itinerary_ids

# Find the cheapest itineraries (price field assumed to be convertible to float)
cheapest_edreams_price = min(float(entry["price"]) for entry in edreams_data)
cheapest_kiwi_price = min(float(entry["price"]) for entry in kiwi_data)

# Get Kiwi itineraries cheaper than the cheapest eDreams itinerary (global minimum)
cheaper_kiwi_itineraries = [entry["id"] for entry in kiwi_data if float(entry["price"]) < cheapest_edreams_price]

# Print basic analysis results
print("ANALYSIS OF MAD-NYC RT")
print(f"Total Kiwi itineraries: {len(kiwi_itinerary_ids)}")
print(f"Total eDreams itineraries: {len(edreams_itinerary_ids)}")
print(f"Repeated itineraries: {len(repeated_itineraries)}")
print(f"Missing in eDreams: {len(missing_in_edreams)}")
print(f"Missing in Kiwi: {len(missing_in_kiwi)}")
print(f"Cheapest eDreams price: {cheapest_edreams_price}")
print(f"Cheapest Kiwi price: {cheapest_kiwi_price}")
print(f"Kiwi itineraries cheaper than cheapest eDreams: {len(cheaper_kiwi_itineraries)}")

# ----------------- Repeated Itineraries Price Comparison -----------------
# For repeated itineraries, compare prices between eDreams and Kiwi.
eDreams_cheaper_count = 0
kiwi_cheaper_count = 0
price_diff_sum = 0  # Sum of (eDreams price - Kiwi price) over all repeated itineraries
# Separate lists for differences when each OTA is cheaper:
eDreams_cheaper_diffs = []  # When eDreams is cheaper: (kiwi_price - edreams_price)
kiwi_cheaper_diffs = []     # When Kiwi is cheaper: (edreams_price - kiwi_price)

for itinerary_id in repeated_itineraries:
    # Find the itinerary's price in both datasets.
    edreams_price = float(next(entry["price"] for entry in edreams_data if entry["id"] == itinerary_id))
    kiwi_price = float(next(entry["price"] for entry in kiwi_data if entry["id"] == itinerary_id))
    price_diff = edreams_price - kiwi_price  # Positive if eDreams is more expensive
    price_diff_sum += price_diff
    if edreams_price < kiwi_price:
        eDreams_cheaper_count += 1
        eDreams_cheaper_diffs.append(kiwi_price - edreams_price)
    elif kiwi_price < edreams_price:
        kiwi_cheaper_count += 1
        kiwi_cheaper_diffs.append(edreams_price - kiwi_price)

total_repeated = len(repeated_itineraries)
percent_eDreams_cheaper_repeated = 100 * eDreams_cheaper_count / total_repeated if total_repeated else 0
percent_kiwi_cheaper_repeated = 100 * kiwi_cheaper_count / total_repeated if total_repeated else 0
overall_avg_price_diff = price_diff_sum / total_repeated if total_repeated else 0
avg_diff_eDreams_cheaper = sum(eDreams_cheaper_diffs) / len(eDreams_cheaper_diffs) if eDreams_cheaper_diffs else 0
avg_diff_kiwi_cheaper = sum(kiwi_cheaper_diffs) / len(kiwi_cheaper_diffs) if kiwi_cheaper_diffs else 0

print("\nAmong repeated itineraries:")
print(f"  Percentage of times eDreams was cheaper: {percent_eDreams_cheaper_repeated:.2f}%")
print(f"  Percentage of times Kiwi was cheaper: {percent_kiwi_cheaper_repeated:.2f}%")
print(f"  Overall average price difference (eDreams - Kiwi): {overall_avg_price_diff:.2f}")
print(f"  Average price difference when eDreams is cheaper (Kiwi price - eDreams price): {avg_diff_eDreams_cheaper:.2f}")
print(f"  Average price difference when Kiwi is cheaper (eDreams price - Kiwi price): {avg_diff_kiwi_cheaper:.2f}")

# ----------------- Overall Kiwi Cheaper Percentage (New Calculation) -----------------
# We calculate the percentage of Kiwi itineraries that are cheaper than eDreams,
# considering:
# 1. Kiwi itineraries (not repeated) that are cheaper than the global cheapest eDreams price.
# 2. Among repeated itineraries, those where Kiwi was cheaper.
not_repeated_kiwi = kiwi_itinerary_ids - repeated_itineraries
count_non_repeated_kiwi = sum(1 for entry in kiwi_data if entry["id"] in not_repeated_kiwi and float(entry["price"]) < cheapest_edreams_price)
numerator = count_non_repeated_kiwi + kiwi_cheaper_count
total_itineraries = len(kiwi_data) + len(edreams_data)
percent_kiwi_cheaper_overall = 100 * numerator / total_itineraries

print(f"\nPercentage of Kiwi itineraries cheaper than eDreams (overall): {percent_kiwi_cheaper_overall:.2f}%")

# ----------------- Price Distribution Graph -----------------
edreams_prices = [float(entry["price"]) for entry in edreams_data]
kiwi_prices = [float(entry["price"]) for entry in kiwi_data]

plt.figure(figsize=(10, 6))
bins = 30  # Adjust as needed
plt.hist(edreams_prices, bins=bins, color='blue', alpha=0.6, label='eDreams')
plt.hist(kiwi_prices, bins=bins, color='green', alpha=0.6, label='Kiwi')
plt.xlabel('Price')
plt.ylabel('Frequency')
plt.title('Price Distribution: eDreams (blue) vs Kiwi (green)')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig("price_distribution.png")
plt.show()

# ----------------- Segments Distribution Graph -----------------
edreams_segments = []
for entry in edreams_data:
    segments, _ = extract_segments_and_carriers(entry["id"])
    if segments is not None:
        edreams_segments.append(segments)

kiwi_segments = []
for entry in kiwi_data:
    segments, _ = extract_segments_and_carriers(entry["id"])
    if segments is not None:
        kiwi_segments.append(segments)

plt.figure(figsize=(10, 6))
bins = range(min(edreams_segments + kiwi_segments), max(edreams_segments + kiwi_segments) + 2)
plt.hist(edreams_segments, bins=bins, color='blue', alpha=0.6, label='eDreams', align='left')
plt.hist(kiwi_segments, bins=bins, color='green', alpha=0.6, label='Kiwi', align='left')
plt.xlabel('Number of Segments')
plt.ylabel('Frequency')
plt.title('Segments Distribution per Itinerary: eDreams (blue) vs Kiwi (green)')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.xticks(np.arange(min(edreams_segments + kiwi_segments),
                      max(edreams_segments + kiwi_segments) + 2, 1))
plt.savefig("segments_distribution.png")
plt.show()

# ----------------- Carriers Distribution Graph -----------------
edreams_carriers = []
for entry in edreams_data:
    _, carriers = extract_segments_and_carriers(entry["id"])
    if carriers is not None:
        edreams_carriers.append(carriers)

kiwi_carriers = []
for entry in kiwi_data:
    _, carriers = extract_segments_and_carriers(entry["id"])
    if carriers is not None:
        kiwi_carriers.append(carriers)

plt.figure(figsize=(10, 6))
bins = range(min(edreams_carriers + kiwi_carriers), max(edreams_carriers + kiwi_carriers) + 2)
plt.hist(edreams_carriers, bins=bins, color='blue', alpha=0.6, label='eDreams', align='left')
plt.hist(kiwi_carriers, bins=bins, color='green', alpha=0.6, label='Kiwi', align='left')
plt.xlabel('Number of Carriers per Itinerary')
plt.ylabel('Frequency')
plt.title('Carriers Distribution per Itinerary: eDreams (blue) vs Kiwi (green)')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.xticks(np.arange(min(edreams_carriers + kiwi_carriers),
                      max(edreams_carriers + kiwi_carriers) + 2, 1))
plt.savefig("carriers_distribution.png")
plt.show()

# ----------------- Optional: Save Sets to Files -----------------
with open("kiwi_itineraries.json", "w") as file:
    json.dump(list(kiwi_itinerary_ids), file, indent=4)

with open("edreams_itineraries.json", "w") as file:
    json.dump(list(edreams_itinerary_ids), file, indent=4)

with open("repeated_itineraries.json", "w") as file:
    json.dump(list(repeated_itineraries), file, indent=4)

with open("missing_in_edreams.json", "w") as file:
    json.dump(list(missing_in_edreams), file, indent=4)

with open("missing_in_kiwi.json", "w") as file:
    json.dump(list(missing_in_kiwi), file, indent=4)

with open("cheaper_kiwi_itineraries.json", "w") as file:
    json.dump(list(cheaper_kiwi_itineraries), file, indent=4)