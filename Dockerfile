FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir plexapi requests Pillow rapidfuzz
COPY plex_logos.py .
CMD ["python", "plex_logos.py"]