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
  Iterate over captured network requests in reverse order (most recent first)
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


def main():
  # Define the itinerary.
  itineraries = [
    ("madrid-spain", "new-york-city-new-york-united-states", "2025-06-14", "2025-06-15"),
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
      while True:
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
        output_file = "final_response.json"
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
    driver.quit()


if __name__ == "__main__":
  main()