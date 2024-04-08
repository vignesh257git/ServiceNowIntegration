import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# ServiceNow Developer Instance credentials
instanceName = os.getenv('INSTANCE_NAME')
username = os.getenv('SNUSERNAME')
password = os.getenv('SNPASSWORD')


# API endpoint for retrieving open incidents
INCIDENT_API_ENDPOINT = f'https://{instanceName}/api/now/table/incident'


# API endpoint for creating incident resolutions
#RESOLUTION_API_ENDPOINT = f'https://{instanceName}/api/now/table/incident'
# API endpoint for creating incident resolutions
RESOLUTION_API_ENDPOINT = f'https://{instanceName}/api/now/table/incident_resolution'


# Function to authenticate and fetch open incidents from ServiceNow
def fetch_open_incidents():
    # Set up authentication headers
    headers = {
        'Accept': 'application/json',
    }
    auth = (username, password)

    # Make a GET request to the incident API endpoint
    response = requests.get(INCIDENT_API_ENDPOINT, headers=headers, auth=auth, params={'sysparm_query': 'active=true'})

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        incidents = response.json().get('result')
        return incidents
    else:
        print(f'Error fetching open incidents: {response.status_code}')
        return None

# Function to automatically generate resolutions for routine issues
def generate_resolution(incident):
    # Check if the incident description contains keywords indicating routine issues
    description = incident.get('description', '')
    keywords = ['routine', 'regular', 'common']
    if any(keyword in description.lower() for keyword in keywords):
        # Automatically generate a resolution for routine issues
        resolution = "This is a routine issue. Please follow the standard procedure to resolve it."
        return resolution
    else:
        return None

# Function to create incident resolutions in ServiceNow
def create_resolution(incident, resolution):
    # Set up authentication headers
    headers = {
        'Content-Type': 'application/json',
    }
    auth = (username, password)

    # Construct payload for creating resolution
    payload = {
        'description': resolution,
        'incident': incident.get('sys_id')
    }

    # Make a POST request to the resolution API endpoint
    response = requests.post(RESOLUTION_API_ENDPOINT, headers=headers, auth=auth, json=payload)

    # Check if the request was successful (status code 201)
    if response.status_code == 201:
        print(f'Resolution created for incident: {incident.get("number")}')
    else:
        print(f'Error creating resolution for incident {incident.get("number")}: {response.status_code}')

# Main function
def main():
    # Fetch open incidents from ServiceNow
    open_incidents = fetch_open_incidents()
    if open_incidents:
        print(f'Found {len(open_incidents)} open incidents:')
        for incident in open_incidents:
            print(f'- {incident.get("number")}: {incident.get("short_description")}')
            # Automatically generate resolution for routine issues
            resolution = generate_resolution(incident)
            if resolution:
                # Create resolution in ServiceNow
                create_resolution(incident, resolution)
    else:
        print('No open incidents found.')

if __name__ == "__main__":
    main()
