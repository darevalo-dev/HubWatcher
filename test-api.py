import requests

# API endpoint
url = "https://api.skypicker.com/umbrella/v2/graphql?featureName=SearchReturnItinerariesQuery"

# Introspection Query
introspection_query = """
query IntrospectionQuery {
  __schema {
    types {
      name
      kind
      description
      fields {
        name
        description
        args {
          name
          type {
            name
            kind
          }
          description
        }
        type {
          name
          kind
        }
      }
      inputFields {
        name
        type {
          name
          kind
        }
        description
      }
      interfaces {
        name
      }
      enumValues {
        name
        description
      }
      possibleTypes {
        name
      }
    }
  }
}
"""

# Headers
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Payload
payload = {
    "query": introspection_query
}

# Send the POST request
response = requests.post(url, json=payload, headers=headers)

# Print the response
if response.status_code == 200:
    print("Schema retrieved successfully!")
    print(response.json())
else:
    print(f"Failed to fetch schema: {response.status_code}")
    print(response.text)