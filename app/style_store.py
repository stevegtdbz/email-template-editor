import json
from pathlib import Path

_PATH = Path.home() / ".email_template_styles.json"


def load() -> list[dict]:
    if not _PATH.exists():
        return []
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save(sets: list[dict]) -> None:
    _PATH.write_text(json.dumps(sets, indent=2), encoding="utf-8")
