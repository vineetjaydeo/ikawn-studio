# Changelog

## v0.1.0 (2026-11-03)
First public release: talking-head reels.
- Web UI: photo or video + script → voice (stock or cloned) → lip-synced 9:16 MP4 with burned captions; 480p preview, HD/FHD final.
- BYOK: per-request Runware key (`X-Runware-Key`, kept in the browser), `IKAWN_BYOK_ONLY=1` for public hosts.
- Max-spend guard on the web API (HTTP 402) as well as the CLI/agent API; estimate shown before every render.
- Word-level captions from local faster-whisper (CPU, free), script spelling preserved; proportional fallback.
- Agent surfaces: CLI, JSON HTTP API (`/v1/<tool>`), MCP server; avatar profiles, looks, voice clone, cost ledger.
- Pronunciation map for TTS (default iKawn → "Eye-kon", extras via `IKAWN_PRONOUNCE` / `IKAWN_PRONOUNCE_FILE`); captions keep script spelling and brand casing.
- Offline mock provider (`STUDIO_PROVIDER=mock`) for tests and demos.
- `/healthz`, upload size limit, clearer errors, key redaction in error messages.
- Docker image runs as non-root, honours `$PORT`, bakes the Whisper model; pinned requirements.
- Free hosting configs: Hugging Face Spaces (Docker) and Render.
