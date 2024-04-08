import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
import openai
import requests

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

openai.api_key  = os.getenv('OPENAI_API_KEY')
gptModel = os.getenv('OPENAI_MODEL')
client = OpenAI()

# ServiceNow Instance credentials
instanceName = os.getenv('INSTANCE_NAME')
username = os.getenv('SNUSERNAME')
password = os.getenv('SNPASSWORD')

# API endpoint for retrieving open incidents
INCIDENT_API_ENDPOINT = f'https://{instanceName}/api/now/table/incident'
logger.info('INCIDENT_API_ENDPOINT: ' + INCIDENT_API_ENDPOINT)
# Initialize OpenAI client
openai.api_key = os.getenv('OPENAI_API_KEY')

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
        logger.error(f'Error fetching open incidents: {response.status_code}')
        return None

# Function to generate text using OpenAI's API
def generate_text(prompt):
    response = client.completions.create(
        model=gptModel,
        prompt=prompt,
        max_tokens=100,
        temperature=0.7
    )
    logger.info("Comments: " + response.choices[0].text.strip())
    return response.choices[0].text.strip()

def add_comment(incident_sys_id,incident_no):
    # Generate comment using OpenAI
    comment = generate_text("Incident update for sys_id: " + incident_sys_id)
    
    # Set up authentication headers
    headers = {
        'Content-Type': 'application/json',
    }
    auth = (username, password)

    # Construct payload for adding a comment
    payload = {
        'comments': comment,
        'incident': incident_sys_id
    }

    # Make a POST request to add the comment
    incident_url= f'{INCIDENT_API_ENDPOINT}/{incident_sys_id}'
    response = requests.post(INCIDENT_API_ENDPOINT, headers=headers, auth=auth, json=payload)

    # Check if the request was successful (status code 201)
    if response.status_code == 201:
        logger.info(f'Comment added to incident: {incident_sys_id}')
        logger.info(f'Incident#: {incident_no}')
    else:
        logger.error(f'Error adding comment to incident {incident_sys_id}: {response.status_code}')



# Function to resolve an incident
def resolve_incident(incident_sys_id):
    resolution_notes = generate_text("Resolution notes for incident with sys_id: " + incident_sys_id)
    payload = {
        'close_code': 'Resolved by request',
        'close_notes': resolution_notes,
        'state': '6',  # Resolved state
    }
    cPayload = {
        'state': '7' # Closed state
    }
    resolve_url = f'{INCIDENT_API_ENDPOINT}/{incident_sys_id}'
    response = requests.patch(resolve_url, json=payload, auth=(username, password))  # Use PATCH method for updating the incident
    if response.status_code == 200:
        logger.info(f'Incident resolved: {incident_sys_id}')
        response = requests.patch(resolve_url, json=cPayload, auth=(username, password)) 
        if response.status_code == 200:
          logger.info(f'Incident closed: {incident_sys_id}')
        else:
          logger.error(f'Error closing incident {incident_sys_id}: {response.status_code}')
          logger.error(response.text)  # Log the response content for debugging

    else:
        logger.error(f'Error resolving incident {incident_sys_id}: {response.status_code}')
        logger.error(response.text)  # Log the response content for debugging

# def read_incident_details():
#     # Fetch open incidents from ServiceNow
#     open_incidents = fetch_open_incidents()
    
#     if open_incidents:
#         # Select the first open incident
#         first_incident = open_incidents[0]
        
#         # Display all fields and their values
#         logger.info("Incident Details:")
#         for field, value in first_incident.items():
#             logger.info(f"{field}: {value}")

#         # Define a dictionary of mandatory fields and their display names
#         mandatory_fields = {
#             'number': 'Incident Number',
#             'short_description': 'Short Description',
#             'state': 'State',
#             'priority': 'Priority',
#             'assignment_group': 'Assignment Group'
#         }
        
#         # Display mandatory fields and their values
#         logger.info("Mandatory Incident Fields:")
#         for field, display_name in mandatory_fields.items():
#             if field in first_incident and first_incident[field]:
#                 value = first_incident[field]
#                 logger.info(f"{display_name}: {value}")
#             else:
#                 logger.warning(f"Missing or empty value for mandatory field '{display_name}'.")
#     else:
#         logger.info('No open incidents found.')



# Main function
def main():
    # Read details of the first open incident
    # read_incident_details()
    # Fetch open incidents from ServiceNow
    open_incidents = fetch_open_incidents()
    # if open_incidents:
    #     # Select the first open incident
    #     first_incident = open_incidents[0]

    if open_incidents:
        logger.info(f'Found {len(open_incidents)} open incidents:')
        for incident in open_incidents:
            shortdesc = incident.get("short_description")
            incState = incident.get("state")
            logger.info(f'- {incident.get("number")}: {shortdesc}')
            if shortdesc == '':
            
            # Add comments to incidents
            # add_comment(incident.get('sys_id'))
            # # Resolve incidents
            # resolve_incident(incident.get('sys_id'))
        # add_comment(first_incident.get('sys_id'),first_incident.get('number'))
            # Resolve incidents
              resolve_incident(incident.get('sys_id'))
              incState = 7
              logger.info(f'Closing the Incident# {incident.get("number")}')

    else:
        logger.info('No open incidents found.')

if __name__ == "__main__":
    main()
