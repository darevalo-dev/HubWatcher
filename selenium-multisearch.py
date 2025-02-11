import time
import json
import re
import glob
import numpy as np
import matplotlib.pyplot as plt
import csv
import brotli  # For Brotli decompression
import hashlib
from seleniumwire import webdriver  # selenium-wire extends Selenium
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
from concurrent.futures import ThreadPoolExecutor, as_completed


# -----------------------------
# Helper Functions (Shared)
# -----------------------------
def load_json(file_path):
  with open(file_path, "r", encoding="utf-8") as file:
    return json.load(file)


def accept_cookies(driver, timeout=10):
  """Wait for and click the 'Accept' button in the cookies popup."""
  try:
    button = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((
          By.XPATH,
          "//div[contains(@class, 'orbit-button-primitive-content') and contains(text(), 'Accept')]"
        ))
    )
    button.click()
    print("Cookie acceptance button clicked.")
  except Exception as e:
    print("Cookie acceptance button not found/clickable.", e)


def search_flights(driver, origin, destination, depart_date, return_date=None):
  """Open the Kiwi.com flight search page and dismiss cookies."""
  base_url = "https://www.kiwi.com/en/search/results"
  search_url = f"{base_url}/{origin}/{destination}/{depart_date}"
  if return_date:
    search_url += f"/{return_date}"
  print(f"Navigating to: {search_url}")
  driver.get(search_url)
  time.sleep(3)  # Allow page to load
  accept_cookies(driver)
  time.sleep(5)  # Wait for initial network requests


def get_network_response(driver, target_url):
  """
  Iterate over captured network requests (most recent first)
  to find the final response matching the target URL, decompress if needed,
  and parse it as JSON.
  """
  for request in reversed(driver.requests):
    if target_url in request.url:
      if request.response:
        raw = request.response.body  # bytes
        encoding = request.response.headers.get('content-encoding', '').lower()
        if 'br' in encoding:
          try:
            decompressed = brotli.decompress(raw)
            text = decompressed.decode('utf-8', errors='replace')
          except Exception as e:
            print("Error decompressing Brotli:", e)
            continue
        else:
          text = raw.decode('utf-8', errors='replace')
        try:
          json_data = json.loads(text)
          return json_data
        except Exception as e:
          print("Error parsing JSON:", e)
          continue
  print("Target network response not found.")
  return None


def click_load_more(driver, timeout=10):
  """Wait for and click the 'Load more' button."""
  try:
    button = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((
          By.XPATH,
          "//button[.//div[text()='Load more']]"
        ))
    )
    button.click()
    print("Clicked 'Load more' button.")
    return True
  except TimeoutException:
    print("Load more button not found or not clickable.")
    return False


def no_more_results_displayed(driver, timeout=5):
  """Return True if the 'No More Results' element is present."""
  try:
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[@data-test='NoMoreResults']"))
    )
    print("No more results detected.")
    return True
  except TimeoutException:
    return False


# -----------------------------
# Main Search Function for One Itinerary
# -----------------------------
def search_and_save(itinerary, output_prefix):
  """
  Runs a flight search for a single itinerary using Selenium,
  clicks 'Load more' until no more results appear,
  then captures the network response from the target URL and writes it to a JSON file.

  Parameters:
    itinerary: a tuple (origin, destination, depart_date, return_date)
    output_prefix: a string to prefix output filenames (e.g. based on itinerary)
  """
  origin, destination, depart_date = itinerary[:3]
  return_date = itinerary[3] if len(itinerary) > 3 else None

  target_network_url = "https://api.skypicker.com/umbrella/v2/graphql?featureName=SearchReturnItinerariesQuery"

  options = webdriver.ChromeOptions()
  # You can add further options here if needed.
  driver = webdriver.Chrome(
      service=ChromeService(ChromeDriverManager().install()),
      options=options
  )

  try:
    search_flights(driver, origin, destination, depart_date, return_date)
    while True:
      if no_more_results_displayed(driver):
        print("Ending loop: no more results available.")
        break
      driver.requests.clear()
      if not click_load_more(driver):
        print("Unable to click 'Load more', ending loop.")
        break
      time.sleep(7)
    final_json = get_network_response(driver, target_network_url)
    if final_json is not None:
      output_file = f"{output_prefix}_final_response.json"
      with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(final_json, f, indent=2, ensure_ascii=False)
      print(f"Final JSON response saved to {output_file}")
    else:
      print("Final network response not found.")
  finally:
    time.sleep(5)
    driver.quit()


# -----------------------------
# Run Multiple Searches in Parallel
# -----------------------------
# Invent 10 long-haul itineraries (these are just examples).
itineraries = [
  (
  "london-united-kingdom", "new-york-city-new-york-united-states", "2025-07-01",
  "2025-07-10"),
  ("madrid-spain", "tokyo-japan-1", "2025-08-05", "2025-08-15"),
  ("paris-france", "sydney-new-south-wales-australia", "2025-09-10", "2025-09-20"),
  (
  "frankfurt-germany", "los-angeles-california-united-states", "2025-10-01", "2025-10-11"),
  ("dubai-united-arab-emirates", "san-francisco-california-united-states", "2025-11-05",
   "2025-11-15")#,
  #("doha-qatar", "seattle-washington-united-states", "2025-12-01", "2025-12-10"),
  #("istanbul-turkey", "chicago-illinois-united-states", "2026-01-10", "2026-01-20"),
  #("rome-italy", "hong-kong-hong-kong-1", "2026-02-15", "2026-02-25"),
  #("amsterdam-netherlands", "melbourne-victoria-australia", "2026-03-05", "2026-03-15"),
  #("dubai-united-arab-emirates", "toronto-ontario-canada", "2026-04-01", "2026-04-10")
]

# We'll use ThreadPoolExecutor to run up to 10 searches concurrently.
with ThreadPoolExecutor(max_workers=10) as executor:
  futures = []
  for idx, itin in enumerate(itineraries, start=1):
    # Create a unique output prefix for each itinerary.
    output_prefix = f"itinerary_{idx}"
    future = executor.submit(search_and_save, itin, output_prefix)
    futures.append(future)
  # Optionally, wait for all tasks to complete.
  for future in as_completed(futures):
    try:
      future.result()
    except Exception as e:
      print("An error occurred during a search:", e)