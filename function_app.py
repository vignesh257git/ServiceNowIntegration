import datetime
import logging
import time
import azure.functions as func
import os
from dotenv import load_dotenv
import openai
from openai import OpenAI
from operator import itemgetter
import requests
import json
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns

app = func.FunctionApp()

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Add a file handler for logging
file_handler = logging.FileHandler('AIticketMaster.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

openai.api_key = os.getenv('OPENAI_API_KEY')
gptModel = os.getenv('OPENAI_MODEL')
client = OpenAI()

# ServiceNow Instance credentials
instanceName = os.getenv('INSTANCE_NAME')
username = os.getenv('SNUSERNAME')
password = os.getenv('SNPASSWORD')
default_assignment_group = os.getenv('DEFAULT_ASSIGNMENT_GROUP')
default_assignee = os.getenv('DEFAULT_ASSIGNEE')
default_caller = os.getenv('CALLER')

# Log credentials to ensure they are loaded correctly
logger.info(f"INSTANCE_NAME: {instanceName}")
#logger.info(f"SNUSERNAME: {username}")
#logger.info(f"SNPASSWORD: {'*' * len(password)}")

# API endpoint for retrieving open incidents
INCIDENT_API_ENDPOINT = f'https://{instanceName}/api/now/table/incident'
logger.info('INCIDENT_API_ENDPOINT: ' + INCIDENT_API_ENDPOINT)

# Set up authentication headers and credentials globally
headers = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
}
auth = (username, password)

# Global variables to track metrics
total_incidents_processed = 0
total_time_taken = 0
total_errors_encountered = 0

@app.schedule(schedule="0 */15 * * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False) 
def AITicketMaster(myTimer: func.TimerRequest) -> None:

   # logger.info(f"INSTANCE_NAME: {instanceName}")
   # logger.info(f"SNPASSWORD: {'*' * len(password)}")
   # logger.info('INCIDENT_API_ENDPOINT: ' + INCIDENT_API_ENDPOINT)
    global total_incidents_processed
    global total_time_taken
    global total_errors_encountered
    if myTimer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function executed.')

    def get_display_value(url, auth, headers):
        response = requests.get(url, auth=auth, headers=headers)
        if response.status_code == 200:
            return response.json().get('result', {}).get('name', 'N/A')
        return 'N/A'
    
    def getFieldNameFromLink(field):
        if isinstance(field, dict):
            field_url = field.get('link')
            field_display_value = get_display_value(field_url, auth, headers) if field_url else 'N/A'
        else:
            field_display_value = 'N/A' # Handle the case when the link does not exist to show N/A otherwise it will throw error

        return field_display_value

    # Function to fetch mandatory fields from incident configuration in ServiceNow
    def get_mandatory_fields():
        # Assuming these are the mandatory fields in your ServiceNow instance
        return ['short_description','description','caller_id','assignment_group','assigned_to']

    # Function to authenticate and fetch open incidents from ServiceNow
    def fetch_open_incidents():
        #Sorting incdients based on creation date in ascending order
        params = {
        'sysparm_query': 'active=true^state!=6',
        'sysparm_order': 'sys_created_on:asc'
        }
        # Make a GET request to the incident API endpoint
        # response = requests.get(INCIDENT_API_ENDPOINT, headers=headers, auth=auth, params={'sysparm_query': 'active=true'})
        response = requests.get(INCIDENT_API_ENDPOINT, headers=headers, auth=auth, params=params)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            incidents = response.json().get('result')
            # Sort incidents by creation date (ascending) and then by priority (descending)
            sorted_incidents = sorted(incidents, key=lambda x: x['sys_created_on'], reverse=False)
            logger.info('Incidents sorted by creation date (ascending)')
            return sorted_incidents
        
        else:
            logger.error(f'Error fetching open incidents: {response.status_code} - {response.text}')
            return None

    # Function to verify and update incident priority based on ticket data
    def verify_and_update_priority(incident_sys_id, incident_info):

        logger.info("Inside verify_and_update_priority method")
        # Rules for priority verification
        # Access requests should have priority between 3 to 5
        def is_access_request(description, short_description):
            keywords = ["access", "request","permission"]
            return any(keyword in description.lower() or keyword in short_description.lower() for keyword in keywords)

        def determine_correct_priority(description, short_description):
            if is_access_request(description, short_description):
                correct_impact = 2
                correct_urgency = 3
                return [correct_impact, correct_urgency]  # Return impact and urgency as a list
            return None  # Return None if no adjustment needed

        current_priority = incident_info['priority']
        current_impact = incident_info['impact']
        current_urgency = incident_info['urgency']
        description = incident_info['description']
        short_description = incident_info['short_description']

        correct_pValues = determine_correct_priority(description, short_description)
        if correct_pValues:
            correct_impact, correct_urgency = correct_pValues
            # Only update if any value is different
            if current_impact != correct_impact or current_urgency != correct_urgency:
                payload = {
                    'impact': correct_impact,
                    'urgency': correct_urgency
                }
                # Make a PATCH request to update the incident priority
                incident_url = f'{INCIDENT_API_ENDPOINT}/{incident_sys_id}'
                response = requests.patch(incident_url, headers=headers, auth=auth, json=payload)

                # Check if the request was successful (status code 200)
                if response.status_code == 200:
                    # Fetch the updated incident details
                    response_get = requests.get(incident_url, headers=headers, auth=auth)
                    if response_get.status_code == 200:
                        updated_incident = response_get.json().get('result', {})
                        updated_priority = updated_incident.get('priority')
                        logger.info(f'Incident priority updated to {updated_priority} for {incident_info["number"]}')
                    else:
                        logger.error(f'Error fetching updated incident details for INC# {incident_info["number"]} - Sysid: {incident_sys_id}: {response_get.status_code}')
                else:
                    logger.error(f'Error updating impact and urgency for INC# {incident_info["number"]} - Sysid: {incident_sys_id}: {response.status_code}')
            else:
                logger.info(f'Impact and urgency for INC# {incident_info["number"]} are correct or no change needed.')
        else:
            logger.info(f'No adjustment needed for INC# {incident_info["number"]}')
    # Function to extract field information from Service Now INCs
    def extract_field_info(incident, sys_id):

        logger.info("Extracting field information")

        assignedTo = incident.get('assigned_to')
        assignedToField = getFieldNameFromLink(assignedTo)
        assignmentgroup = incident.get('assignment_group')
        assignmentGroupField = getFieldNameFromLink(assignmentgroup)
        incState = int(incident.get('state'))
        incNo = incident.get('number')
        description = incident.get('description')
        short_description = incident.get('short_description')
        priority = incident.get('priority')
        caller = incident.get('caller_id')
        callerField = getFieldNameFromLink(caller)

        # Dictionary of mandatory fields and their display names
        display_fields = {
            'number': 'Incident Number',
            'short_description': 'Title',
            'description': 'Description',
            'state': 'State',
            'priority': 'Priority',
            'assignment_group': 'Assignment Group',
            'assigned_to': 'Assigned To',
            'caller_id': 'Caller'
        }

        # Display mandatory fields and their values
        for field, display_name in display_fields.items():
            if field == 'assigned_to':
                logger.info(f"Assigned To: {assignedToField}")
            elif field == 'assignment_group':
                logger.info(f"Assignment Group: {assignmentGroupField}")
            elif field == 'caller_id':
                logger.info(f"Caller: {callerField}")
            elif field in incident and incident[field]:
                value = incident[field]
                logger.info(f"{display_name}: {value}")
            else:
                logger.warning(f"Missing or empty value for field '{display_name}'.")

        # Creating a dictionary with incident information
        incident_info = {
            'sys_id': sys_id,
            'state': incState,
            'number': incNo,
            'description': description,
            'short_description': short_description,
            'priority': priority
        }

        # Creating custom fields u_automation_time_stamp and u_lock_duration in ServiceNow Incidents
        u_automation_time_stamp = incident.get('u_automation_time_stamp')
        u_lock_duration = incident.get('u_lock_duration')

        logger.info(f"Automation Time Stamp: {u_automation_time_stamp}")
        logger.info(f"Lock Duration: {u_lock_duration}")
        if u_automation_time_stamp and u_lock_duration:
            last_automation_time = datetime.strptime(u_automation_time_stamp, '%Y-%m-%d %H:%M:%S')
            u_lock_duration_timedelta = timedelta(minutes=int(u_lock_duration))
            
            if datetime.now() < last_automation_time + u_lock_duration_timedelta:
                logger.info(f'Incident {incident.get("number")} is locked and will not be processed again.')
                return
    
        # Verify and update priority if necessary
        verify_and_update_priority(sys_id, incident)
        # Call the method of check and fill the mandatory fields
        check_and_fill_mandatory_fields(sys_id, incident)
        # Call the method to update the incident state
        update_incident_state(sys_id, incident_info)
        # Update the u_automation_time_stamp field
        update_automation_timestamp(sys_id)

    # Function to check and fill mandatory fields in a ServiceNow incident
    def check_and_fill_mandatory_fields(sys_id, incident):
        logger.info("Inside check_and_fill_mandatory_fields method....")
        mandatory_fields = get_mandatory_fields()
        missing_fields = []

        for field in mandatory_fields:
            if not incident.get(field):
                missing_fields.append(field)
                
        if missing_fields:
            logger.warning(f'Missing mandatory fields: {missing_fields}')

            payload = {}

            # Replace with actual logic to fill missing fields
            for field in missing_fields:
                if field in ['short_description','description']:
                    #incident[field] = 'Default Short Description'
                    resolve_incident(sys_id)
                elif field == 'assignment_group':
                    payload[field] = default_assignment_group
                elif field == 'assigned_to':
                    payload[field] = default_assignee
                elif field == 'caller_id':
                    payload[field] = default_caller

            if payload:
                # Update the incident in ServiceNow
                incident_url = f'{INCIDENT_API_ENDPOINT}/{sys_id}'
                response = requests.patch(incident_url, headers=headers, auth=auth, json=payload)

                if response.status_code == 200:
                    logger.info('Incident updated successfully with default values.')
                else:
                    logger.error(f'Error updating incident: {response.status_code} - {response.text}')

        else:
            logger.info('All mandatory fields are provided.')

    # Function to update incident state
    def update_incident_state(incident_sys_id, incident_info):

        # Dictionary to map state numbers to state names
        state_names = {
            1: 'New',
            2: 'In Progress',
            3: 'On Hold',
            6: 'Resolved',
            7: 'Closed'
        }

        incState = incident_info['state']
        incNo = incident_info['number']
        description = incident_info['description']
        short_description = incident_info['short_description']
        priority = incident_info['priority']

        logger.info("Inside update_incident_state method")
        if incState in (1, 3):  # New or On Hold state
            new_state = 2  # In Progress state
        elif incState == 2:  # In Progress state
            new_state = 3  # On Hold state
            add_comment(incident_sys_id, incNo, description, short_description,priority)
        else:
            new_state = None
        

        if new_state is not None:
            if new_state == 3:
                payload = {
                           'state': new_state,
                           'hold_reason': 1
                           }
            else:
                payload = {'state': new_state}
            # Make a PATCH request to update the incident state
            incident_url = f'{INCIDENT_API_ENDPOINT}/{incident_sys_id}'
            response = requests.patch(incident_url, headers=headers, auth=auth, json=payload)
            # Check if the request was successful (status code 200)
            if response.status_code == 200:
                state_name = state_names.get(new_state, 'Unknown')
                logger.info(f'Incident state updated to \'{state_name}\' for {incNo}')
                #logger.info(f'Incident state updated to {new_state} for {incNo}')
            else:
                logger.error(f'Error updating incident state for INC# {incNo} - Sysid: {incident_sys_id}: {response.status_code}')


    # Function to generate text using OpenAI's API
    def generate_text(description, short_description,priority):
        logger.info("Inside generate_text method..")
        response = client.completions.create(
                model=gptModel,
                #prompt=prompt,
                prompt=description + '\n' + short_description,
                max_tokens=50,
                temperature=0.7
            )
        logger.info("Comments: " + response.choices[0].text.strip())
        return response.choices[0].text.strip()
    # Function to add comment to incident
    def add_comment(incident_sys_id, incident_no, description, short_description,priority):

        logger.info("Inside add_comment method..")
           # Generate comment using OpenAI
        comment = generate_text(description,short_description,priority)

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
    def resolve_incident(incident_sys_id,priority):
        resolution_notes = generate_text("Resolution notes for incident with sys_id: " + incident_sys_id, "Closure:", priority)
        payload = {
            'close_code': 'Resolved by request',
            'close_notes': resolution_notes,
            'state': '6',  # Resolved state
        }

        resolve_url = f'{INCIDENT_API_ENDPOINT}/{incident_sys_id}'
        response = requests.patch(resolve_url, json=payload, auth=auth)  # Use PATCH method for updating the incident
        if response.status_code == 200:
            logger.info(f'Incident resolved: {incident_sys_id}')
        else:
            logger.error(f'Error resolving incident {incident_sys_id}: {response.status_code}')
            logger.error(response.text)  # Log the response content for debugging

    def close_incident(incident_sys_id):
        close_url = f'{INCIDENT_API_ENDPOINT}/{incident_sys_id}'
        cPayload = {
            'state': '7'  # Closed state
        }
        response = requests.patch(close_url, json=cPayload, auth=auth)
        if response.status_code == 200:
            logger.info(f'Incident closed: {incident_sys_id}')
        else:
            logger.error(f'Error closing incident {incident_sys_id}: {response.status_code}')
            logger.error(response.text)  

    # Function to update automation timestamp
    def update_automation_timestamp(incident_sys_id):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        payload = {
            'u_automation_time_stamp': timestamp
        }
        update_url = f'{INCIDENT_API_ENDPOINT}/{incident_sys_id}'
        response = requests.patch(update_url, headers=headers, auth=auth, json=payload)
        
        if response.status_code == 200:
            logger.info(f'Updated u_automation_time_stamp for incident: {incident_sys_id}')
        else:
            logger.error(f'Error updating u_automation_time_stamp for incident {incident_sys_id}: {response.status_code}')
            logger.error(response.text)  # Log the response content for debugging

    # Function to log metrics
    def log_metrics():
        # Log metrics such as number of incidents processed, time taken, errors encountered, etc.
        # Example metrics:
        metrics = {
            'Total Incidents Processed': total_incidents_processed,  # Replace with actual count
            'Average Time Taken Per Incident Update': total_time_taken / total_incidents_processed ,  # Replace with actual time taken
            'Total Errors Encountered': total_errors_encountered  # Replace with actual count
        }
        logger.info(f'Metrics: {metrics}')
        #Call generate_visual_report method
        generate_visual_report(metrics)

    def generate_visual_report(metrics):

        names = list(metrics.keys())
        values = list(metrics.values())

        fig, ax = plt.subplots(figsize=(10, 6))
        sns.barplot(x=names, y=values, ax=ax)
        ax.set_title('Metrics Summary')
        ax.set_ylabel('Count/Time')
        ax.set_xlabel('Metrics')
        plt.xticks(rotation=45)
        plt.legend(['Service Now Incidents AI Integration Metrics'])

        plt.tight_layout()
        plt.savefig('metrics.png')
        plt.show()

    # Fetch open incidents from ServiceNow
    open_incidents = fetch_open_incidents()

    if open_incidents:
        logging.info(f'Found {len(open_incidents)} open incidents:')
        for incident in open_incidents:
            
            logger.info(f"{incident.get('number')} --- {incident.get('sys_created_on')} --- P{incident.get('priority')}")

        # Process each incident
        # Select the first open incident
        #incident = open_incidents[0]
        #top_incidents = open_incidents[:1]
        top_incidents = open_incidents[:5]

        for incident in top_incidents:
            inc_sys_id = incident.get('sys_id')
            inc_priority = incident.get('priority')
            incNo = incident.get('number')

            start_time = time.time()  # Start time for processing an incident
            logger.info(f"Processing INC# {incNo}: Start time --- {start_time}")
            try:
                # Extract information from INC fields and update comments
                extract_field_info(incident, inc_sys_id)

                # Resolve and close the first incident
                #resolve_incident(inc_sys_id,inc_priority)
                #close_incident(inc_sys_id)
            except Exception as e:
                total_errors_encountered += 1
                logger.error(f'Error updating incident {incident.get("number")}: {str(e)}')
            end_time = time.time()  # End time for processing an incident
            logger.info(f"Completed Processing INC# {incNo}: End time --- {end_time}")
            total_incidents_processed += 1
            total_time_taken += (end_time - start_time)

        avg_time_per_incident = total_time_taken / total_incidents_processed if total_incidents_processed else 0
                    
        # Call log_metrics method to collect the log metrics                
        log_metrics()

    else:
        logging.info('No open incidents found.')
