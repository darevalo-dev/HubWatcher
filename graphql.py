import requests

# API endpoint
url = "https://api.skypicker.com/umbrella/v2/graphql?featureName=SearchReturnItinerariesQuery"

# Simplified GraphQL query
query = """
query SearchReturnItinerariesQuery($search: SearchReturnInput, $filter: ItinerariesFilterInput, $options: ItinerariesOptionsInput) {
  returnItineraries(search: $search, filter: $filter, options: $options) {
    __typename
    ... on AppError {
      error: message
    }
    ... on Itineraries {
      server {
        requestId
        environment
        packageVersion
        serverToken
      }
      metadata {
        carriers {
          code
          id
        }
        itinerariesCount
        hasMorePending
      }
      itineraries {
        __typename
        id
        shareId
        price {
          amount
          priceBeforeDiscount
        }
        priceEur {
          amount
        }
        provider {
          name
          code
        }
      }
    }
  }
}
"""

# Variables
variables = {
    "filter": {
        "allowReturnFromDifferentCity": True,
        "allowChangeInboundDestination": True,
        "allowChangeInboundSource": True,
        "allowDifferentStationConnection": True,
        "contentProviders": ["KIWI", "FRESH", "KAYAK", "WEGO", "U2_META_API"],
        "enableSelfTransfer": True,
        "enableThrowAwayTicketing": True,
        "enableTrueHiddenCity": True,
        "flightsApiLimit": 25,
        "limit": 80,
        "transportTypes": ["FLIGHT"]
    },
    "options": {
        "sortBy": "QUALITY",
        "mergePriceDiffRule": "INCREASED",
        "currency": "eur",
        "locale": "en",
        "market": "es",
        "partner": "skypicker",
        "searchSessionId": "3c494b886b7d497db623869cbb31a29f",
        "serverToken": "eyJyb2xlcyI6...",  # Replace with a valid token
        "sortVersion": 11,
        "applySortingChanges": True,
        "abTestInput": {
            "priceElasticityGuarantee": "ENABLE",
            "baggageProtectionBundle": "ENABLE",
            "kayakWithoutBags": "DISABLE"
        }
    },
    "search": {
        "itinerary": {
            "source": {
                "ids": ["City:madrid_es"]
            },
            "destination": {
                "ids": ["Station:airport:PMI"]
            }
        },
        "cabinClass": {
            "cabinClass": "ECONOMY",
            "applyMixedClasses": False
        },
        "passengers": {
            "adults": 1,
            "children": 0,
            "infants": 0
        }
    }
}

# Headers
headers = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "es-ES,es;q=0.9,en;q=0.8",
    "content-type": "application/json",
    "kw-skypicker-visitor-uniqid": "81433e3a-0b19-462a-b7e1-c55ab802655d",  # Replace with a valid value
    "kw-umbrella-token": "87439d04cf7d66290725c51f3f93cbfeed337017174215ed0d6d4486e71b61cb",  # Replace with a valid value
    "origin": "https://www.kiwi.com",
    "referer": "https://www.kiwi.com/",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}

# Payload
payload = {
    "query": query,
    "variables": variables
}

# Send the POST request
response = requests.post(url, json=payload, headers=headers)

# Process the response
if response.status_code == 200:
    print("Response data:")
    print(response.json())
else:
    print(f"Request failed with status code {response.status_code}")
    print(response.text)