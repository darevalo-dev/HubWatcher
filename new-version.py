import asyncio
from playwright.async_api import async_playwright


async def fetch_flight_data(origin, destination, departure_date,
    return_date=None):
  url = f"https://www.kiwi.com/en/search/results/{origin}/{destination}/{departure_date}"

  if return_date:
    url += f"/{return_date}"

  async with async_playwright() as p:
    # Launch Chrome
    browser = await p.chromium.launch(
      headless=False)  # Set to False to see the browser
    context = await browser.new_context()
    page = await context.new_page()

    print(f"Navigating to: {url}")
    await page.goto(url)

    # Listen to network requests
    async def handle_request(response):
      if "graphql?featureName=SearchReturnItinerariesQuery" in response.url:
        try:
          json_data = await response.json()
          print("\n--- Flight Data JSON ---\n")
          print(json_data)
        except:
          print("Error parsing JSON")

    page.on("response", handle_request)

    # Wait for some time to capture responses
    await page.wait_for_timeout(10000)  # 10 seconds

    # Close browser
    await browser.close()


# Test the script with different routes
async def main():
  await fetch_flight_data("madrid-spain", "palma-de-mallorca-palma-spain",
                          "2025-06-14")



# Run the script
asyncio.run(main())