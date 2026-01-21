#!/usr/bin/env python3
"""Generate a minimal PDF to verify IBMPlexSans-Light rendering."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

from utils.pathing import get_base_path

try:
    import pdfkit
except ImportError as exc:
    print(f"pdfkit not available: {exc}")
    sys.exit(1)


def main() -> int:
    base_dir = get_base_path(__file__)
    reports_dir = base_dir / "reports"
    reports_dir.mkdir(exist_ok=True)

    font_path = base_dir / "IBMPlexSans-Light.ttf"
    if not font_path.exists():
        print(f"Required font missing: {font_path}")
        return 1

    font_url = font_path.resolve().as_posix()
    html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    @font-face {{
      font-family: 'IBMPlexSans-Light';
      src: url('file:///{font_url}') format('truetype');
      font-weight: 300;
      font-style: normal;
    }}
    body {{
      font-family: 'IBMPlexSans-Light', Arial, sans-serif;
      font-size: 12pt;
    }}
  </style>
</head>
<body>
  <h1>IBMPlexSans-Light Smoke Test</h1>
  <p>Umlaut probe: ÄÖÜäöüß</p>
  <p>Generated: {datetime.now().isoformat(sep=' ', timespec='seconds')}</p>
</body>
</html>
"""

    output = reports_dir / "font_smoke.pdf"
    try:
        pdfkit.from_string(
            html,
            str(output),
            options={"enable-local-file-access": None, "encoding": "UTF-8"},
        )
    except OSError as exc:
        print(f"wkhtmltopdf not available: {exc}")
        return 1

    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
