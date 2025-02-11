import pyautogui
import webbrowser
import time

# Open the Vueling website in Google Chrome
url = "https://www.vueling.com/en"
webbrowser.open(url)

# Wait for the browser to load fully
print("Opening the browser and loading the website...")
time.sleep(5)  # Adjust the sleep time based on your internet speed

# Coordinates extracted from the image
coordinates = {
    "from_field": (0, 604),  # Top-left corner (x, y)
    "to_field": (0, 265),
    "outbound_field": (4, 686),
    "return_field": (4, 648),
    "search_button": (5, 737)
}


# Step 1: Click on the "From" field and type "MAD" for Madrid
pyautogui.click(*coordinates["from_field"])
pyautogui.write("MAD")
time.sleep(1)

# Step 2: Click on the "To" field and type "PMI" for Palma de Mallorca
pyautogui.click(*coordinates["to_field"])
pyautogui.write("PMI")
time.sleep(1)

# Step 3: Click on the "Outbound" date field and select next Friday
pyautogui.click(*coordinates["outbound_field"])
# Use the arrow keys or a direct click to select the correct date (e.g., next Friday)
pyautogui.press("tab", presses=3)  # Adjust the number of presses to reach the correct date
pyautogui.press("enter")

# Step 4: Click on the "Return" date field and select next Sunday
pyautogui.click(*coordinates["return_field"])
# Use the arrow keys or a direct click to select the correct date (e.g., next Sunday)
pyautogui.press("tab", presses=5)  # Adjust the number of presses to reach the correct date
pyautogui.press("enter")

# Step 5: Ensure "1 Passenger" is already selected
# If not, you can add steps to click on the passenger selection field and adjust it.

# Step 6: Click the "Search" button
pyautogui.click(*coordinates["search_button"])

print("Search initiated.")
