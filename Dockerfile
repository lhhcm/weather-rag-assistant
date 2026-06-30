FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV WEATHER_SERVER_HOST=0.0.0.0
ENV WEATHER_SERVER_PORT=7860
ENV WEATHER_USER_DATA_DIR=/data/weather_users

WORKDIR /app

COPY requirements-space.txt .
RUN pip install --no-cache-dir -r requirements-space.txt

COPY data data
COPY src src
COPY static static

EXPOSE 7860

CMD ["python", "-m", "src.weather_rag.server"]
