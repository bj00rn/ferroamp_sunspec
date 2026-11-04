FROM python:3.11-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY configuration.py device.py server.py telemetry.py mqtt.py ferroamp_sunspec.py ./

ENTRYPOINT ["python", "ferroamp_sunspec.py"]