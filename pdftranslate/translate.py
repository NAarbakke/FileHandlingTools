"""Stage 2: translate each non-skip block via Ollama, with an on-disk cache."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"

LANG_NAMES = {"en": "English", "no": "Norwegian (Bokmål)"}

SYSTEM_PROMPT = (
    "You are a professional translator. Translate the user's text from {src} to {tgt}. "
    "Output ONLY the translation, with no preamble, notes, or quotation marks. "
    "Preserve numbers, units, math, and inline formatting. "
    "Leave proper nouns, acronyms, and citation markers unchanged."
)


class OllamaTranslator:
    """Callable translator backed by a local Ollama chat model."""

    def __init__(self, model="gemma2:9b", url=OLLAMA_URL, src="en", tgt="no", temperature=0.2, timeout=300):
        self.model = model
        self.url = url
        self.timeout = timeout
        self.temperature = temperature
        self.system = SYSTEM_PROMPT.format(
            src=LANG_NAMES.get(src, src), tgt=LANG_NAMES.get(tgt, tgt)
        )

    def __call__(self, text):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system},
                {"role": "user", "content": text},
            ],
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["message"]["content"].strip()


def cache_key(model, src, tgt, text):
    raw = f"{model}\x00{src}\x00{tgt}\x00{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def translate_document(doc, translator, cache_dir=None, progress=None):
    """Add `text_translated` to every non-skip block. Mutates and returns `doc`."""
    src, tgt = doc["source_lang"], doc["target_lang"]
    model = getattr(translator, "model", "mock")
    cache = Path(cache_dir) if cache_dir else None
    if cache:
        cache.mkdir(parents=True, exist_ok=True)

    pending = [b for p in doc["pages"] for b in p["blocks"] if not b.get("skip")]
    total = len(pending)
    for done, blk in enumerate(pending, start=1):
        text = blk["text"]
        cfile = cache / f"{cache_key(model, src, tgt, text)}.txt" if cache else None
        if cfile is not None and cfile.exists():
            translated = cfile.read_text(encoding="utf-8")
        else:
            translated = translator(text)
            if cfile is not None:
                cfile.write_text(translated, encoding="utf-8")
        blk["text_translated"] = translated
        if progress:
            progress(done, total)
    return doc


def run(blocks_path, out_path, *, model="gemma2:9b", cache_dir=None, translator=None, progress=None):
    doc = json.loads(Path(blocks_path).read_text(encoding="utf-8"))
    if translator is None:
        translator = OllamaTranslator(model=model, src=doc["source_lang"], tgt=doc["target_lang"])
    translate_document(doc, translator, cache_dir=cache_dir, progress=progress)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc
