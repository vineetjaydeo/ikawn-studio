"""Cost estimates (USD) from Runware's published per-second / per-character rates (Nov 2026)."""
from providers.runware import MODELS, TTS, UPSCALER
WPS = 2.6  # spoken words per second, used to estimate length from the script
def est_seconds(script): return max(2.0, len(script.split()) / WPS)
def estimate(script, model="heygen:avatar@4", voice_model="heygen:voice@1.0-turbo-free"):
    s = est_seconds(script); rates = MODELS[model][2]; tts = TTS[voice_model] * len(script)
    gen = lambda tier: rates.get(tier) or max(rates.values())
    preview = round(tts + gen("480p" if "480p" in rates else min(rates)) * s, 4)
    final = {}
    for tier in ("720p", "1080p"):
        regen = round(tts + gen(tier) * s, 4); up = round(UPSCALER[1][tier] * s, 4)
        final[tier] = {"regenerate": regen, "upscale_preview": up,
                       "recommended": "upscale_preview" if up < regen * 0.5 else "regenerate"}
    return {"seconds": round(s, 1), "preview_480p": preview, "final": final}
