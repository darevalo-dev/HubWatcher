import json
import sys

def remove_duplicates(input_file, output_file):
    """
    Removes duplicate itinerary entries from the JSON file based on the 'id' field.
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as file:
            data = json.load(file)

        # Use a dictionary to store unique itineraries
        unique_itineraries = {}
        for entry in data:
            itinerary_id = entry.get("id")
            if itinerary_id and itinerary_id not in unique_itineraries:
                unique_itineraries[itinerary_id] = entry

        # Convert dictionary values back to a list
        cleaned_data = list(unique_itineraries.values())

        # Write the cleaned data to the output file
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(cleaned_data, file, indent=4, ensure_ascii=False)

        print(f"Duplicates removed. Output saved to {output_file} with {len(cleaned_data)} unique itineraries.")
    except Exception as e:
        print(f"Error processing the file: {e}")

if __name__ == "__main__":
        input_file = "kiwi-simplified.json"
        output_file = "kiwi-simplified-filtered.json"
        remove_duplicates(input_file, output_file)
