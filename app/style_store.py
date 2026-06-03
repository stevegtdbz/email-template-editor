import json
from pathlib import Path

_STYLES_PATH   = Path.home() / ".email_template_styles.json"
_CLASSES_PATH  = Path.home() / ".email_template_classes.json"
_OPENAI_PATH   = Path.home() / ".email_template_openai.json"
_PANEL_PATH    = Path.home() / ".email_template_panel.json"


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


# ── OpenAI API key ────────────────────────────────────────────────────────────

def load_openai_key() -> str:
    if not _OPENAI_PATH.exists():
        return ""
    try:
        return json.loads(_OPENAI_PATH.read_text(encoding="utf-8")).get("key", "")
    except Exception:
        return ""


def save_openai_key(key: str) -> None:
    _OPENAI_PATH.write_text(json.dumps({"key": key}, indent=2), encoding="utf-8")


# ── Editor panel collapse state ───────────────────────────────────────────────

_SECTION_DEFAULTS = {
    "attrs":       False,
    "style":       False,
    "ai":          True,
    "style_sets":  False,
    "css_classes": False,
}


def load_section_states() -> dict:
    if not _PANEL_PATH.exists():
        return dict(_SECTION_DEFAULTS)
    try:
        saved = json.loads(_PANEL_PATH.read_text(encoding="utf-8"))
        merged = dict(_SECTION_DEFAULTS)
        merged.update({k: v for k, v in saved.items() if k in _SECTION_DEFAULTS})
        return merged
    except Exception:
        return dict(_SECTION_DEFAULTS)


def save_section_states(states: dict) -> None:
    _PANEL_PATH.write_text(json.dumps(states, indent=2), encoding="utf-8")
