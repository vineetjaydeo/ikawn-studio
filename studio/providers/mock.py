"""Offline mock provider (STUDIO_PROVIDER=mock): no network, no spend. Returns file:// URLs to sample clips
so the full pipeline (UI -> API -> captions -> MP4) can be tested without a key."""
import os, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2] / "samples"
VIDEO = os.environ.get("IKAWN_MOCK_VIDEO", str(ROOT / "avatar_raw_480p.mp4"))
class Mock:
    def __init__(self): self.cost = 0.0
    def tts(self, text, voice=None, model=None, language="en", clone_sample=None):
        return "file://mock-audio", ("mock-voice-id" if clone_sample else None)
    def _v(self): return pathlib.Path(VIDEO).as_uri()
    def lipsync(self, base_video, audio_url, model=None, settings=None): return self._v()
    def avatar(self, image, audio_url, model=None, tier="480p"): return self._v()
    def upscale(self, url): return self._v()
