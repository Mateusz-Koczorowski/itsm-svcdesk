# svcdesk image, started from the template's Dockerfile.example.
# Every dependency is installed at build time; nothing is fetched at run time (API.md section 9).
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/ /app/src/

RUN mkdir -p /data
ENV SVCDESK_DB=/data/svcdesk.db
ENV PYTHONUNBUFFERED=1

EXPOSE 8080
CMD ["uvicorn", "svcdesk.main:app", "--app-dir", "/app/src", "--host", "0.0.0.0", "--port", "8080"]
