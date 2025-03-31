FROM python:3.9.21-alpine

# Install Python and pip
RUN apk add --no-cache python3 py3-pip

# Add application files to the container
ADD . /app

# Install dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Set the working directory
WORKDIR /app

# Set the default port as a build argument and environment variable
ARG PORT=502
ENV PORT=${PORT}


# Use ferroamp_sunspec.py as the entry point
CMD python3 ferroamp_sunspec.py --modbus-port $PORT --mqtt-host $MQTT_HOST