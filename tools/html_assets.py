"""Utilities for externalizing generated HTML assets."""

import re
from pathlib import Path


def externalize_html_assets(
    html: str,
    output_html: Path,
    css_filename: str,
    js_filename: str,
) -> str:
    """Write inline style/script blocks beside an HTML artifact and link them."""
    output_html = Path(output_html)
    output_html.parent.mkdir(parents=True, exist_ok=True)

    style_match = re.search(r"<style(?:\s[^>]*)?>(?P<body>.*?)</style>", html, re.DOTALL)
    if style_match is None:
        raise ValueError("Generated HTML does not contain a style block")

    script_matches = list(
        re.finditer(r"<script(?![^>]*\bsrc=)(?:\s[^>]*)?>(?P<body>.*?)</script>", html, re.DOTALL)
    )
    if not script_matches:
        raise ValueError("Generated HTML does not contain an inline script block")

    script_match = script_matches[-1]
    (output_html.parent / css_filename).write_text(
        style_match.group("body").strip() + "\n", encoding="utf-8"
    )
    (output_html.parent / js_filename).write_text(
        script_match.group("body").strip() + "\n", encoding="utf-8"
    )

    html = html[: style_match.start()] + (
        f'<link rel="stylesheet" href="{css_filename}">'
    ) + html[style_match.end() :]
    # Re-find the inline script after replacing the style block because its offset changed.
    updated_scripts = list(
        re.finditer(r"<script(?![^>]*\bsrc=)(?:\s[^>]*)?>(?P<body>.*?)</script>", html, re.DOTALL)
    )
    updated_script = updated_scripts[-1]
    html = html[: updated_script.start()] + (
        f'<script src="{js_filename}" defer></script>'
    ) + html[updated_script.end() :]
    return html
