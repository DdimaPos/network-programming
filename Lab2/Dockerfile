FROM python:3.13-slim

WORKDIR /app

COPY serverMultithread.py ./
COPY content ./content

EXPOSE 8080

CMD ["python", "serverMultithread.py", "content", "8080"]
