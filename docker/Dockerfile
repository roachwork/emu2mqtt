FROM python:3.12-alpine

WORKDIR /app

HEALTHCHECK CMD [ "test", "-f", "/app/healthcheck" ]

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY emu2mqtt/* .

ENTRYPOINT ["python", "."]