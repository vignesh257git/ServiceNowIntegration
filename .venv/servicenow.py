import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
import openai
import requests
import json

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

openai.api_key = os.getenv('OPENAI_API_KEY')
gptModel = os.getenv('OPENAI_MODEL')
client = OpenAI()

# ServiceNow Instance credentials
instanceName = os.getenv('INSTANCE_NAME')
username = os.getenv('SNUSERNAME')
password = os.getenv('SNPASSWORD')

# API endpoint for retrieving open incidents
INCIDENT_API_ENDPOINT = f'https://{instanceName}/api/now/table/incident'
# API endpoint for retrieving assignment group names
ASSIGNMENT_GROUP_ENDPOINT = f'https://{instanceName}/api/now/table/sys_user_group'
# API endpoint for retrieving the users from the assignment group
ASSIGNEE_ENDPOINT = f'https://{instanceName}/api/now/table/sys_user'
logger.info('INCIDENT_API_ENDPOINT: ' + INCIDENT_API_ENDPOINT)

# Set up authentication headers and credentials globally
headers = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
}
auth = (username, password)

# Initialize OpenAI client
openai.api_key = os.getenv('OPENAI_API_KEY')

# Function to authenticate and fetch open incidents from ServiceNow
def fetch_open_incidents():
    # Make a GET request to the incident API endpoint
    response = requests.get(INCIDENT_API_ENDPOINT, headers=headers, auth=auth, params={'sysparm_query': 'active=true'})

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        incidents = response.json().get('result')
        return incidents
    else:
        logger.error(f'Error fetching open incidents: {response.status_code}')
        return None

# Function to extract field information from Service Now INCs
def extract_field_info(incident, sys_id):
    print("Extracting field information")
    assignedTo = incident.get('assigned_to')
    incState = int(incident.get('state'))
    incNo = incident.get('number')
    description = incident.get('description')
    short_description = incident.get('short_description')
    # Display all fields and their values
    # logger.info("Incident Details:")
    # for field, value in incident.items():
    #     logger.info(f"{field}: {value}")

    # Define a dictionary of mandatory fields and their display names
    mandatory_fields = {
        'number': 'Incident Number',
        'short_description': 'Short Description',
        'description': 'Description',
        'state': 'State',
        'priority': 'Priority',
        'assignment_group': 'Assignment Group',
        'assigned_to': 'Assigned To'
    }
    payload = {}

    #Calling get_assignment_group method
    assignment_groups = get_assignment_group(sys_id)
    if assignment_groups:
        print("Assignment Groups:")
        for name, sys_id in assignment_groups:
            print(f"Name: {name}, ID: {sys_id}")
    else:
        print("Failed to fetch assignment groups.")

    # Display mandatory fields and their values
    for field, display_name in mandatory_fields.items():
        if field in incident and incident[field]:
            value = incident[field]
            logger.info(f"{display_name}: {value}")
        else:
            logger.warning(f"Missing or empty value for mandatory field '{display_name}'.")
    # Update incident state based on current state
    if incState in (1,3):  # New state
        # Construct payload for updating the state to In Progress


        payload = {
            'state': 2  # In Progress state
        }

        
        #update_incident_state(sys_id, payload)
    elif incState == 2:  # In Progress state
        # Construct payload for updating the state to On Hold

        payload = {
            'state': 3  # On Hold state
        }

        #Calling add_comment method to update the comments in INC
        add_comment(sys_id,incNo,description,short_description)
        #Calling update_incident_state method to update the INC status
    update_incident_state(sys_id, payload)

def get_assignment_group(sys_id):
   # incident_url = f'{INCIDENT_API_ENDPOINT}/{sys_id}'
    # Define parameters to filter only assignment groups
    params = {'sysparm_query': 'type=assignment_group', 'sysparm_fields': 'name,sys_id'}
    try:
        # Make the GET request
        response = requests.get(ASSIGNMENT_GROUP_ENDPOINT, auth=auth, params=params)
        logger.info("***********Inside try block of get_assignment_group")
        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()
            logger.info('****8After data')

            # Extract assignment group names and IDs
            assignment_groups = [(group['name'], group['sys_id']) for group in data['result']]
            logger.info('****8After assignment groups in if')
            return assignment_groups
        else:
            # If the request was not successful, print the error message
            print(f"Error: {response.status_code} - {response.text}")
            logger.info('****8After assignment groups in else')
            return None
    except Exception as e:
        # Print any exceptions that occur during the request
        print(f"An error occurred: {str(e)}")
        return None

# Function to update incident state
def update_incident_state(incident_sys_id, payload):
    # Make a PATCH request to update the incident state
    incident_url = f'{INCIDENT_API_ENDPOINT}/{incident_sys_id}'
    response = requests.patch(incident_url, headers=headers, auth=auth, json=payload)
    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        logger.info(f'Incident state updated: {incident_sys_id}')
    else:
        logger.error(f'Error updating incident state {incident_sys_id}: {response.status_code}')

                
           # if assignedTo.empty:

# Function to generate text using OpenAI's API
def generate_text(description,short_description):
    response = client.completions.create(
        model=gptModel,
        #prompt=prompt,
        prompt=description + '\n' + short_description,
        max_tokens=100,
        temperature=0.7
    )
    logger.info("Comments: " + response.choices[0].text.strip())
    return response.choices[0].text.strip()

def add_comment(incident_sys_id, incident_no,description,short_description):
    # Generate comment using OpenAI
    comment = generate_text(description,short_description)

    # Construct payload for adding a comment
    payload = {
        'comments': comment,
        'incident': incident_sys_id
    }

    # Make a patch request to add the comment
    incident_url = f'{INCIDENT_API_ENDPOINT}/{incident_sys_id}'
    response = requests.patch(incident_url, headers=headers, auth=auth, json=payload)
    logger.info(f'Incident#: {incident_no}')
    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        logger.info(f'Comment added to incident: {incident_sys_id}')
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
        'state': '7'  # Closed state
    }
    resolve_url = f'{INCIDENT_API_ENDPOINT}/{incident_sys_id}'
    response = requests.patch(resolve_url, json=payload, auth=auth)  # Use PATCH method for updating the incident
    if response.status_code == 200:
        logger.info(f'Incident resolved: {incident_sys_id}')
        response = requests.patch(resolve_url, json=cPayload, auth=auth)
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
    # Fetch open incidents from ServiceNow
    open_incidents = fetch_open_incidents()
    if open_incidents:
        # Select the first open incident
        first_incident = open_incidents[0]

    # if open_incidents:
    #     logger.info(f'Found {len(open_incidents)} open incidents:')
    #     for incident in open_incidents:
    #         shortdesc = incident.get("short_description")
    #         incState = incident.get("state")
    #         logger.info(f'- {incident.get("number")}: {shortdesc}')
            # if shortdesc == '':

        # Extract information from INC fields
        extract_field_info(first_incident,first_incident.get('sys_id'))
            
            # Add comments to incidents
            # add_comment(incident.get('sys_id'))
       # add_comment(first_incident.get('sys_id'),first_incident.get('number'))
            # # Resolve incidents
            # resolve_incident(incident.get('sys_id'))
        # add_comment(first_incident.get('sys_id'),first_incident.get('number'))
            # Resolve incidents
            #   resolve_incident(incident.get('sys_id'))

    else:
        logger.info('No open incidents found.')

if __name__ == "__main__":
    main()
