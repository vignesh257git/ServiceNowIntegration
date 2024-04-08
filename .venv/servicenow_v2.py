import os
import requests
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# OpenAI API key
openai_api_key = os.getenv('OPENAI_API_KEY')
gptModel = os.getenv('OPENAI_MODEL')
# ServiceNow Developer Instance credentials
instanceName = os.getenv('INSTANCE_NAME')
username = os.getenv('SNUSERNAME')
password = os.getenv('SNPASSWORD')

# API endpoint for retrieving open incidents
INCIDENT_API_ENDPOINT = f'https://{instanceName}/api/now/table/incident'

# API endpoint for creating incident resolutions
RESOLUTION_API_ENDPOINT = f'https://{instanceName}/api/now/table/incident'

client =  OpenAI()

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

# Function to generate resolution using OpenAI's API
def generate_resolution(incident):
    # Check if the incident description contains keywords indicating routine issues
    description = incident.get('description', '')
    keywords = ['routine', 'regular', 'common']
    if any(keyword in description.lower() for keyword in keywords):
        # Call OpenAI's API to generate response
        prompt = "Incident description: " + description
        response = generate_openai_response(prompt)
        return response
    else:
        return None

# Function to call OpenAI's API and generate response
def generate_openai_response(prompt):
    endpoint = "https://api.openai.com/v1/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token {openai_api_key}"
    }
    data = {
        #"model": "text-davinci-003",  # You can choose any model from OpenAI, such as text-davinci-002
        "model": gptModel,
        "prompt": prompt,
        "max_tokens": 100
    }
    response = requests.post(endpoint, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()["choices"][0]["text"].strip()
    else:
        print(f"Error generating response from OpenAI: {response.status_code}")
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
