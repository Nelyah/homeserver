    # Use an official Python runtime as a parent image
FROM python:slim

# Set the working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY requirements.txt /app

# Create a virtual environment
RUN python -m venv /app/venv && . /app/venv/bin/activate && pip install --upgrade pip && pip install -r /app/requirements.txt

COPY ovh-update-dyndns.py /app

# Ensure the virtual environment is activated before running the script
CMD ["/bin/bash", "-c", ". /app/venv/bin/activate && /app/venv/bin/python /app/ovh-update-dyndns.py"]

