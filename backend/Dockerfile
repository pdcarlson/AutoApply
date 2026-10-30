# One image for both the API and the agent worker.
# The Playwright base image already has Python 3.12 and Chromium installed.
FROM mcr.microsoft.com/playwright/python:v1.48.0-noble

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
