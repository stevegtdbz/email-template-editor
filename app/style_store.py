import json
from pathlib import Path

_STYLES_PATH  = Path.home() / ".email_template_styles.json"
_CLASSES_PATH = Path.home() / ".email_template_classes.json"


# ── Style sets (inline) ───────────────────────────────────────────────────────

def load() -> list[dict]:
    if not _STYLES_PATH.exists():
        return []
    try:
        return json.loads(_STYLES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save(sets: list[dict]) -> None:
    _STYLES_PATH.write_text(json.dumps(sets, indent=2), encoding="utf-8")


# ── CSS classes ───────────────────────────────────────────────────────────────

def load_classes() -> list[dict]:
    """Each entry: {"name": "myclass", "css": "font-size:34px; color:red;"}"""
    if not _CLASSES_PATH.exists():
        return []
    try:
        return json.loads(_CLASSES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_classes(classes: list[dict]) -> None:
    _CLASSES_PATH.write_text(json.dumps(classes, indent=2), encoding="utf-8")
