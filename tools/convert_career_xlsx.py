"""
One-time conversion: IL-2_Tracker_career_award_coordinates.xlsx
             →  IL-2_Tracker_career_award_coordinates.json

Excel format (single sheet):
  - Section-header rows: column A = "USSR (early)" | "USSR (late)" | "USA" |
    "Germany" | "Britain"; column B = "x" (literal header marker)
  - Data rows within each section:
      Col A: medal/overlay name  (e.g. "iron_cross_2nd_big1")
      Col B: x  (integer, top-left pixel)
      Col C: y
      Col D: w  (width)
      Col E: h  (height)
      Col F: unused
      Col G+: replacement chain (higher-tier variants, left=base+1)
  - Overlay rows are identified by the word "overlay" in the name.

Output JSON structure mirrors IL-2_Tracker_award_coordinates.json:
  {
    "ussr_early": {
      "medals": [{"name": "...", "x": 0, "y": 0, "w": 0, "h": 0, "replacements": []}, ...],
      "overlay": {"name": "...", "x": 0, "y": 0, "w": 0, "h": 0, "replacements": []}
    },
    ...
  }
"""

import json
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:
    print("ERROR: openpyxl is required. Install with: pip install openpyxl", file=sys.stderr)
    sys.exit(1)


SECTION_HEADERS: dict[str, str] = {
    'USSR (early)': 'ussr_early',
    'USSR (late)':  'ussr_late',
    'USA':          'usa',
    'Germany':      'germany',
    'Britain':      'britain',
}


def convert(xlsx_path: Path, json_path: Path) -> None:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active

    result: dict[str, dict] = {}
    current_key: str | None = None
    medals: list[dict] = []
    overlay: dict | None = None

    def flush() -> None:
        nonlocal medals, overlay
        if current_key is not None:
            section: dict = {'medals': medals}
            if overlay is not None:
                section['overlay'] = overlay
            result[current_key] = section
        medals = []
        overlay = None

    for row in ws.iter_rows(values_only=True):
        # Skip fully-empty rows
        if not any(v is not None for v in row):
            continue

        name = row[0]

        # Section-header row: column A is a known country name, column B is 'x'
        if name in SECTION_HEADERS:
            flush()
            current_key = SECTION_HEADERS[name]
            medals = []
            overlay = None
            continue

        # Skip if no active section or no name
        if current_key is None or name is None:
            continue

        # Data row: columns B-E must be numeric
        x_val, y_val, w_val, h_val = row[1], row[2], row[3], row[4]
        if not all(isinstance(v, (int, float)) for v in (x_val, y_val, w_val, h_val)):
            continue

        # Replacement chain starts at column G (index 6); skip any None values
        replacements = [str(r).strip() for r in row[6:] if r is not None]

        entry: dict = {
            'name':         str(name).strip(),
            'x':            int(x_val),
            'y':            int(y_val),
            'w':            int(w_val),
            'h':            int(h_val),
            'replacements': replacements,
        }

        if 'overlay' in str(name).lower():
            overlay = entry
        else:
            medals.append(entry)

    # Flush the last section
    flush()

    json_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )

    total_medals = sum(len(v.get('medals', [])) for v in result.values())
    print(
        f"Written {json_path}\n"
        f"  Sections : {list(result.keys())}\n"
        f"  Medals   : {total_medals} total\n"
        f"  Overlays : {sum(1 for v in result.values() if 'overlay' in v)}"
    )


if __name__ == '__main__':
    root = Path(__file__).parent.parent
    xlsx = root / 'IL-2_Tracker_career_award_coordinates.xlsx'
    out  = root / 'IL-2_Tracker_career_award_coordinates.json'

    if not xlsx.exists():
        print(f"ERROR: Source file not found: {xlsx}", file=sys.stderr)
        sys.exit(1)

    convert(xlsx, out)
