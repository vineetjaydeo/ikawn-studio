FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
# non-root user (required by Hugging Face Spaces, good practice elsewhere)
RUN useradd -m -u 1000 app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
ENV HF_HOME=/home/app/.cache/huggingface IKAWN_HOME=/app/data STUDIO_MEDIA=/app/media PORT=8000
USER app
# bake the Whisper "base" model into the image so the first caption job is fast (≈145 MB). Skip with --build-arg WHISPER=0
ARG WHISPER=1
RUN if [ "$WHISPER" = "1" ]; then python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')" || true; fi
COPY --chown=app:app studio studio
COPY --chown=app:app web web
COPY --chown=app:app samples/input_face.jpg samples/avatar_raw_480p.mp4 samples/
RUN mkdir -p /app/data /app/media
WORKDIR /app/studio
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
