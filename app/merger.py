import re
from pathlib import Path


def merge_sections(guide_html: str, content_parts: list[str]) -> str:
    """Replace SECTION:CONTENT in the guide with the supplied HTML parts."""
    joined = '\n'.join(content_parts)
    replacement = (
        '<!-- SECTION:CONTENT -->\n'
        + joined
        + '\n        <!-- /SECTION:CONTENT -->'
    )
    result = re.sub(
        r'<!-- SECTION:CONTENT -->.*?<!-- /SECTION:CONTENT -->',
        replacement,
        guide_html,
        flags=re.DOTALL,
    )
    return result


def load_guide(path: Path) -> str:
    return path.read_text(encoding='utf-8')
