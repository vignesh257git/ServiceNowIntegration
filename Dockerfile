# Use an official Python runtime as the base image
FROM mcr.microsoft.com/azure-functions/python:3.0

# Set the working directory in the container
WORKDIR /home/site/wwwroot

# Copy the Azure Function files to the container
COPY . .

# Install any dependencies needed for your Azure Function (if applicable)
RUN pip install --no-cache-dir -r requirements.txt

# Command to run the Azure Function when the container starts
CMD ["azure-functions", "host", "start"]
