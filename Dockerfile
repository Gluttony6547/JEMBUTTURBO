FROM python:3.12-slim

WORKDIR /app

COPY . .

EXPOSE 5050

CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "5050"]
