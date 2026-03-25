FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir prometheus_client
COPY agent.py .
CMD ["python", "agent.py"]
