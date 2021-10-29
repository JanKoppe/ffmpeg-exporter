FROM python:3.9-alpine
WORKDIR /app
ADD requirements.txt .
RUN pip install -r requirements.txt 
ADD ffmpeg-exporter.py .
ENTRYPOINT python ffmpeg-exporter.py