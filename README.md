# ServiceNow Ticket Automation with OpenAI and Azure Functions

Automate the process of reading and responding to open incidents and service requests in ServiceNow using Azure Functions and OpenAI's completion API. This project fetches open incidents and service requests from ServiceNow, analyzes the data history of previous tickets, and generates responses automatically based on the title and description of the fetched tickets using OpenAI's powerful language model. It can also automatically update comments and resolve tickets based on predefined criteria.

## Features

- Fetch open incidents and service requests from ServiceNow.
- Analyze the data history of previous tickets to generate intelligent responses using OpenAI's completion API.
- Automatically update comments and resolve tickets based on predefined criteria.
- Deployed as an Azure Function for seamless integration with other Azure services.
- Autoscaling with KEDA in Azure Kubernetes Service (AKS) based on the number of open incidents.

## Getting Started

To get started with the project, follow these steps:

1. Clone the repository to your local machine:

   ```bash
   git clone https://github.com/your-username/your-repository.git
Set up your Azure Function environment:

Create a .env file and add your environment variables. You'll need variables for your ServiceNow instance credentials, OpenAI API key, and any other necessary configurations.
Configure the Azure Function to run locally:

Ensure you have the Azure Functions Core Tools installed.
Run the Azure Function locally using the following command:


func start
Test the function locally and make any necessary adjustments.

Deploy the Azure Function to Azure Kubernetes Service (AKS) with KEDA for autoscaling:

Containerize the Azure Function using Docker and push the image to Azure Container Registry (ACR).
Create an AKS cluster if you haven't already.
Install and configure KEDA on your AKS cluster.
Deploy the containerized Azure Function to AKS.
Contributing
Contributions are welcome! If you have any ideas for improvement, feature requests, or bug reports, please open an issue or submit a pull request.
