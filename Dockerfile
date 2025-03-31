FROM python:3.9.21-alpine
RUN apk add --no-cache python3 py3-pip
ADD . /app

RUN pip install --no-cache-dir -r /app/requirements.txt
WORKDIR /app
ARG PORT=502
ENV PORT=${PORT}

CMD python3 server.py --port $PORT