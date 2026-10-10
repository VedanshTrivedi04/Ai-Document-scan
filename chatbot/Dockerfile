FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Render sets Docker context to the repository root.
# Copy requirements and source from the chatbot/ directory.
COPY chatbot/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY chatbot/ ./

EXPOSE 10000

CMD ["python", "bot.py"]
