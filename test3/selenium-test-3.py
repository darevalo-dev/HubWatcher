import time
import json
import brotli  # For Brotli decompression

from seleniumwire import webdriver  # selenium-wire extends Selenium
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException


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
  Iterate over captured network requests, filter by target URL,
  reverse the order (most recent first), and select the best response
  based on the number of results.
  """
  # Filter requests matching the target URL
  filtered_requests = [req for req in driver.requests if
                       target_url in req.url and req.response]

  # Reverse the filtered list
  filtered_requests.reverse()

  # Select the best request based on results
  selected_request = None

  if len(filtered_requests) > 1:
    first_request = filtered_requests[0]
    second_request = filtered_requests[1]

    # Extract JSON from first request to check the number of results
    try:
      raw = first_request.response.body
      encoding = first_request.response.headers.get('content-encoding',
                                                    '').lower()
      if 'br' in encoding:
        raw = brotli.decompress(raw)
      text = raw.decode('utf-8', errors='replace')
      json_data = json.loads(text)

      # If first request has less than 26 results, pick the second as it seems Kiwi is returning the first results otherwise
      if len(json_data.get("results", [])) < 26:
        selected_request = second_request
      else:
        selected_request = first_request
    except Exception as e:
      print("Error processing first request:", e)
      return None
  elif filtered_requests:
    selected_request = filtered_requests[0]  # Only one request, take it

  # Process and return the selected request
  if selected_request:
    try:
      raw = selected_request.response.body
      encoding = selected_request.response.headers.get('content-encoding',
                                                       '').lower()
      if 'br' in encoding:
        raw = brotli.decompress(raw)
      text = raw.decode('utf-8', errors='replace')
      return json.loads(text)
    except Exception as e:
      print("Error parsing JSON:", e)

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


def main():
  # Define the itinerary.
  itineraries = [
    ("barcelona-spain", "paris-france", "2025-02-14", "2025-02-16"),
  ]

  # Target network URL to intercept.
  target_network_url = "https://api.skypicker.com/umbrella/v2/graphql?featureName=SearchReturnItinerariesQuery"

  # Initialize the Chrome WebDriver (using selenium-wire).
  options = webdriver.ChromeOptions()
  driver = webdriver.Chrome(
      service=ChromeService(ChromeDriverManager().install()),
      options=options
  )

  try:
    for itinerary in itineraries:
      origin, destination, depart_date = itinerary[:3]
      return_date = itinerary[3] if len(itinerary) > 3 else None

      # Load initial search results.
      search_flights(driver, origin, destination, depart_date, return_date)

      # Loop: click "Load more" until "No More Results" is present.
      #i = 0
      while True:
        #i = i+1
        #if i >= 5:
        #  break
        if no_more_results_displayed(driver):
          print("Ending loop: no more results available.")
          break

        # Clear previous network requests to capture only new ones.
        driver.requests.clear()

        if not click_load_more(driver):
          print("Unable to click 'Load more', ending loop.")
          break

        time.sleep(7)  # Wait for new network request(s) to fire.

      # After the loop, get the final (aggregated) response.
      final_json = get_network_response(driver, target_network_url)
      if final_json is not None:
        output_file = "kiwi-response.json"
        try:
          with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_json, f, indent=2, ensure_ascii=False)
          print(f"Final JSON response saved to {output_file}")
        except Exception as e:
          print("Error writing final JSON to file:", e)
      else:
        print("Final network response not found.")
  finally:
    time.sleep(5)
    #driver.quit()


if __name__ == "__main__":
  main()