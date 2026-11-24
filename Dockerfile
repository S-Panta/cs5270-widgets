FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY widget_consumer/ ./widget_consumer/
ENTRYPOINT ["python", "-m", "widget_consumer.cli"]
CMD ["--request-queue", "cs5270-requests", "--storage", "dynamodb", "--table", "widgets", "--region", "us-east-1"]