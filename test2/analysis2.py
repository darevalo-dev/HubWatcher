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

# Create hash sets for itineraries (using id field)
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

# Get Kiwi itineraries cheaper than the cheapest eDreams itinerary
cheaper_kiwi_itineraries = [entry["id"] for entry in kiwi_data if float(entry["price"]) < cheapest_edreams_price]

# Print results
print("ANALYSIS OF BCN-DPS RT")
print(f"Total Kiwi itineraries: {len(kiwi_itinerary_ids)}")
print(f"Total eDreams itineraries: {len(edreams_itinerary_ids)}")
print(f"Repeated itineraries: {len(repeated_itineraries)}")
print(f"Missing in eDreams: {len(missing_in_edreams)}")
print(f"Missing in Kiwi: {len(missing_in_kiwi)}")
print(f"Cheapest eDreams price: {cheapest_edreams_price}")
print(f"Cheapest Kiwi price: {cheapest_kiwi_price}")
print(f"Kiwi itineraries cheaper than cheapest eDreams: {len(cheaper_kiwi_itineraries)}")

# ----------------- Price Distribution Graph -----------------
# Extract prices for plotting
edreams_prices = [float(entry["price"]) for entry in edreams_data]
kiwi_prices = [float(entry["price"]) for entry in kiwi_data]

plt.figure(figsize=(10, 6))
bins = 30  # Adjust number of bins as needed
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
# Extract segments from the itinerary id for each entry
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
# Create bins based on the range of segments
bins = range(min(edreams_segments + kiwi_segments), max(edreams_segments + kiwi_segments) + 2)
plt.hist(edreams_segments, bins=bins, color='blue', alpha=0.6, label='eDreams', align='left')
plt.hist(kiwi_segments, bins=bins, color='green', alpha=0.6, label='Kiwi', align='left')
plt.xlabel('Number of Segments')
plt.ylabel('Frequency')
plt.title('Segments Distribution per Itinerary: eDreams (blue) vs Kiwi (green)')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig("segments_distribution.png")
plt.xticks(np.arange(min(edreams_segments + kiwi_segments),
                      max(edreams_segments + kiwi_segments) + 2, 1))
plt.show()

# ----------------- Carriers Distribution Graph -----------------
# Extract carriers count from the itinerary id for each entry
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
# Create bins based on the range of carriers count
bins = range(min(edreams_carriers + kiwi_carriers), max(edreams_carriers + kiwi_carriers) + 2)
plt.hist(edreams_carriers, bins=bins, color='blue', alpha=0.6, label='eDreams', align='left')
plt.hist(kiwi_carriers, bins=bins, color='green', alpha=0.6, label='Kiwi', align='left')
plt.xlabel('Number of Carriers per Itinerary')
plt.ylabel('Frequency')
plt.title('Carriers Distribution per Itinerary: eDreams (blue) vs Kiwi (green)')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig("carriers_distribution.png")
plt.show()

# Optional: Save the sets to files
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