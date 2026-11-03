"""Captions + 9:16 export with ffmpeg.
Captions use word-level timings from local Whisper (faster-whisper, CPU, free) when it is installed;
otherwise they are timed proportionally from the script. Set IKAWN_CAPTIONS=proportional to skip Whisper,
IKAWN_WHISPER_MODEL (default "base") to pick the model size."""
import os, re, subprocess
FONT = next((f for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"] if os.path.exists(f)), None)
TIERS = {"480p": (480, 854), "720p": (720, 1280), "1080p": (1080, 1920)}
_WHISPER = None
def duration(p):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout
    try: return float(out.strip().splitlines()[0])
    except (ValueError, IndexError): return 0.0
def chunks(script, dur, words_per=3):
    w = script.split(); groups = [" ".join(w[i:i+words_per]) for i in range(0, len(w), words_per)]
    chars = sum(len(g) for g in groups) or 1; t, out = 0.0, []
    for g in groups:
        d = dur * len(g) / chars; out.append((round(t, 2), round(t + d, 2), g)); t += d
    return out
def whisper_words(media, lang=None, prompt=None):
    """[(start, end, word)] from local faster-whisper, or None if unavailable/failed."""
    global _WHISPER
    if os.environ.get("IKAWN_CAPTIONS", "whisper") != "whisper": return None
    try:
        from faster_whisper import WhisperModel
        if _WHISPER is None: _WHISPER = WhisperModel(os.environ.get("IKAWN_WHISPER_MODEL", "base"), device="cpu", compute_type="int8")
        import numpy as np  # decode with ffmpeg (avoids PyAV version issues)
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", media, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
        audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
        segs, _ = _WHISPER.transcribe(audio, language=lang, word_timestamps=True, vad_filter=False, initial_prompt=prompt)
        words = [(float(w.start), float(w.end), w.word.strip()) for s in segs for w in (s.words or []) if w.word.strip()]
        return words or None
    except Exception as e:
        print(f"[captions] whisper unavailable ({type(e).__name__}: {e}); using proportional timing"); return None
def word_chunks(words, words_per=3, max_gap=0.6):
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= words_per or w[0] - cur[-1][1] > max_gap): out.append(cur); cur = []
        cur.append(w)
    if cur: out.append(cur)
    return [(round(c[0][0], 2), round(c[-1][1], 2), " ".join(x[2] for x in c)) for c in out]
def align(words, script):
    """Keep Whisper's timings but show the script's spelling (brand names, etc.) wherever the words line up.
    Script words are expanded through the pronunciation map (iKawn -> Eye-kon) so they match what was spoken."""
    import difflib
    from pronounce import spoken
    n = lambda t: re.sub(r"\W", "", t.lower())
    toks = []  # (normalized spoken token, display text or "" for continuation)
    for w in script.split():
        parts = [x for x in re.split(r"[\s-]+", spoken(w)) if n(x)] or [w]
        toks += [(n(parts[0]), w)] + [(n(x), "") for x in parts[1:]]
    wn = []  # whisper words split the same way, keeping timings
    for a, b, t in words:
        ps = [x for x in re.split(r"[\s-]+", t) if n(x)] or [t]
        for i, x in enumerate(ps): wn.append([a + (b - a) * i / len(ps), a + (b - a) * (i + 1) / len(ps), x, n(x)])
    sm = difflib.SequenceMatcher(None, [w[3] for w in wn], [t[0] for t in toks], autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("equal", "replace") and i2 - i1 == j2 - j1:
            for k in range(i2 - i1): wn[i1 + k][2] = toks[j1 + k][1]
    out = []
    for a, b, t, _ in wn:
        if t == "" and out: out[-1] = (out[-1][0], b, out[-1][2])
        elif t: out.append((a, b, t))
    return out
def caption_chunks(video, script, lang=None):
    """Returns (chunks, method). Word timings from Whisper, spelling from the script where they align."""
    words = whisper_words(video, lang, prompt=__import__('pronounce').spoken(script)[:800])
    if words: return word_chunks(align(words, script)), "whisper"
    return chunks(script, duration(video)), "proportional"
def _caps(t):  # uppercase captions, but keep brand casing like "iKawn"
    return " ".join(w if re.search(r"[a-z][A-Z]", w) else w.upper() for w in t.split())
def _esc(t): return re.sub(r"([:\\%,;\[\]])", r"\\\1", t.replace("'", "\u2019"))
def export(video, script, out, tier="480p", lang=None, captions=True):
    W, H = TIERS[tier]; fs = int(W * 0.07); font = f"fontfile={FONT}:" if FONT else ""
    vf = [f"scale={W}:{H}:force_original_aspect_ratio=increase", f"crop={W}:{H}", "setsar=1"]
    method = "none"
    if captions and script:
        cs, method = caption_chunks(video, script, lang)
        for a, b, txt in cs:
            vf.append(f"drawtext={font}text='{_esc(_caps(txt))}':fontsize={fs}:fontcolor=white:borderw={max(3,fs//10)}:bordercolor=black:"
                      f"x=(w-text_w)/2:y=h*0.70:enable='between(t,{a},{b})'")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-vf", ",".join(vf), "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", out], check=True)
    return method
