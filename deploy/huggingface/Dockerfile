# Hugging Face Spaces (Docker SDK, free CPU Basic). Build context = repo root copied into the Space.
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
ENV HF_HOME=/home/user/.cache/huggingface IKAWN_HOME=/app/data STUDIO_MEDIA=/app/media PORT=7860 \
    IKAWN_BYOK_ONLY=1 IKAWN_MAX_SPEND=0.50 IKAWN_MAX_UPLOAD_MB=40
USER user
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')" || true
COPY --chown=user studio studio
COPY --chown=user web web
COPY --chown=user samples/input_face.jpg samples/avatar_raw_480p.mp4 samples/
RUN mkdir -p /app/data /app/media
WORKDIR /app/studio
EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
