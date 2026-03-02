"""
Diagnostic: trace every step of the /api/career/<id>/showcase endpoint.

Usage:
    python tools/diagnose_career_showcase.py <path_to_cp.db> [career_id]

If career_id is omitted, lists all available careers and exits.

Example:
    python tools/diagnose_career_showcase.py "C:/IL-2/data/Career/cp.db"
    python tools/diagnose_career_showcase.py "C:/IL-2/data/Career/cp.db" 12345
"""

import json
import sys
from pathlib import Path

# Allow imports from project root
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    db_path = Path(sys.argv[1])
    career_id_arg: int | None = int(sys.argv[2]) if len(sys.argv) >= 3 else None

    # ------------------------------------------------------------------
    section("1. Imports & Project root")
    # ------------------------------------------------------------------
    print(f"  Project root : {ROOT}")
    print(f"  cp.db        : {db_path}  (exists={db_path.exists()})")

    try:
        from campaign_service_record.career.database import CareerDatabase
        from campaign_service_record.career.chain_resolver import CareerChainResolver
        from campaign_service_record.career.statistics import StatisticsMapper
        from campaign_service_record.career.mission_linker import MissionReportLinker
        from campaign_service_record.career.aggregator import CareerAggregator
        from campaign_service_record.providers.career_provider import CareerDataProvider
        from campaign_service_record.core.medal_showcase import (
            load_career_coordinates,
            resolve_showcase_country,
            resolve_ussr_variant,
            award_image_to_showcase_name,
            build_showcase_data,
            CAREER_CANVAS_FILENAME,
            CAREER_OVERLAY_FILENAME,
        )
        ok("All imports successful")
    except ImportError as exc:
        fail(f"Import failed: {exc}")
        sys.exit(1)

    # ------------------------------------------------------------------
    section("2. Database + provider initialisation")
    # ------------------------------------------------------------------
    if not db_path.exists():
        fail(f"cp.db not found: {db_path}")
        sys.exit(1)

    try:
        db = CareerDatabase(db_path)
        resolver = CareerChainResolver(db)
        stats = StatisticsMapper()
        linker = MissionReportLinker(Path('.'))
        aggregator = CareerAggregator(
            db, resolver, stats, linker,
            game_dir=None, data_dir=None,
        )
        provider = CareerDataProvider(db, resolver, aggregator)
        ok("Provider initialized")
    except Exception as exc:
        fail(f"Initialization failed: {exc}")
        sys.exit(1)

    # ------------------------------------------------------------------
    section("3. Available careers")
    # ------------------------------------------------------------------
    try:
        careers = provider.get_entry_list()
    except Exception as exc:
        fail(f"get_entry_list() raised: {exc}")
        sys.exit(1)

    if not careers:
        warn("No careers returned by get_entry_list()")
    else:
        ok(f"{len(careers)} career(s) found")
        for c in careers:
            flag = " <-- target" if c.get('id') == str(career_id_arg) else ""
            print(f"      id={c.get('id')!r:12}  name={c.get('name')!r}  country={c.get('country')!r}{flag}")

    if career_id_arg is None:
        print("\n  Pass a career_id to diagnose a specific career.")
        sys.exit(0)

    # ------------------------------------------------------------------
    section(f"4. Career detail  (id={career_id_arg})")
    # ------------------------------------------------------------------
    detail = provider.get_entry_detail(str(career_id_arg))
    if detail is None:
        fail(f"get_entry_detail('{career_id_arg}') returned None  →  route returns 404 'Career not found'")
        sys.exit(1)
    ok(f"Detail returned  (keys: {list(detail.keys())})")

    country = detail.get('country', '')
    print(f"  country      : {country!r}")

    events = detail.get('events', [])
    award_events = [ev for ev in events if ev.get('type') == 'award']
    print(f"  total events : {len(events)}  (award events: {len(award_events)})")

    # ------------------------------------------------------------------
    section("5. Country → showcase key")
    # ------------------------------------------------------------------
    showcase_base = resolve_showcase_country(country)
    if not showcase_base:
        fail(f"resolve_showcase_country({country!r}) returned None/empty  →  route returns 404 'Unsupported country'")
    else:
        ok(f"showcase_base = {showcase_base!r}")

    if showcase_base == 'ussr':
        dates = [ev.get('date') for ev in events if ev.get('date')]
        country_key = resolve_ussr_variant(max(dates) if dates else None)
    elif showcase_base:
        country_key = showcase_base
    else:
        country_key = None
    print(f"  country_key  : {country_key!r}")

    # ------------------------------------------------------------------
    section("6. Earned showcase names (from modal_image_url)")
    # ------------------------------------------------------------------
    earned: set[str] = set()
    for ev in award_events:
        modal_url = ev.get('modal_image_url') or ''
        filename  = Path(modal_url).name if modal_url else ''
        name      = award_image_to_showcase_name(filename) if filename else ''
        status    = ok if name else warn
        status(f"modal_image_url={modal_url!r}  →  filename={filename!r}  →  showcase_name={name!r}")
        if name:
            earned.add(name)

    if not award_events:
        warn("No award events found; earned will be empty (showcase opens but no medals lit)")
    ok(f"Earned showcase names ({len(earned)}): {sorted(earned)}")

    # ------------------------------------------------------------------
    section("7. Coordinate JSON search")
    # ------------------------------------------------------------------
    # Mirror exact logic from routes.py  (_career_data_dir = data_dir = CWD)
    data_dir = ROOT     # same as config.data_dir = Path.cwd() in dev mode
    candidates = [
        data_dir / 'IL-2_Tracker_career_award_coordinates.json',
        data_dir.parent / 'IL-2_Tracker_career_award_coordinates.json',
    ]
    career_json: Path | None = None
    for c in candidates:
        print(f"  Checking: {c}  (exists={c.exists()})")
        if c.exists():
            career_json = c
            break

    if career_json is None:
        fail("Career coordinate JSON not found  →  route returns 404 'Career coordinate file not found'")
        fail("Run:  python tools/convert_career_xlsx.py")
    else:
        ok(f"Found: {career_json}")
        try:
            coordinates = load_career_coordinates(career_json)
            ok(f"Coordinates loaded  (keys: {list(coordinates.keys())})")
            if country_key and country_key in coordinates:
                cs = coordinates[country_key]
                ok(f"Country section '{country_key}': {len(cs.medals)} medals, overlay={'yes' if cs.overlay else 'no'}")
            elif country_key:
                fail(f"Country key '{country_key}' NOT in coordinates  (available: {list(coordinates.keys())})")
        except Exception as exc:
            fail(f"load_career_coordinates() raised: {exc}")

    # ------------------------------------------------------------------
    section("8. Assets directory")
    # ------------------------------------------------------------------
    # Derive game_dir from db path (standard IL-2 layout: <game_root>/data/Career/cp.db)
    derived_game_dir = db_path.parent.parent.parent  # up 3 levels from cp.db
    game_dir_candidate = derived_game_dir / 'data' / 'swf' / 'CampaignRanksAwards'

    print(f"  Derived game root  : {derived_game_dir}")
    print(f"  game assets_dir    : {game_dir_candidate}  (exists={game_dir_candidate.exists()})")
    print(f"  data assets_dir    : {data_dir / 'CampaignRanksAwards'}  (exists={(data_dir / 'CampaignRanksAwards').exists()})")

    if game_dir_candidate.exists():
        assets_dir = game_dir_candidate
        ok(f"Using game assets_dir: {assets_dir}")
    elif (data_dir / 'CampaignRanksAwards').exists():
        assets_dir = data_dir / 'CampaignRanksAwards'
        ok(f"Using data assets_dir: {assets_dir}")
    else:
        fail("Neither assets_dir exists  →  all medal files will be missing from response")
        assets_dir = game_dir_candidate   # proceed anyway to show build_showcase_data output

    # Spot-check: does the canvas for this country exist?
    if country_key:
        canvas_name = CAREER_CANVAS_FILENAME.get(country_key, '')
        subfolder   = {
            'ussr_early': 'USSR/early',
            'ussr_late':  'USSR/late',
            'usa':        'USA',
            'germany':    'Germany',
            'britain':    'Britain',
        }.get(country_key, '')
        if canvas_name and subfolder:
            canvas_path = assets_dir / subfolder / canvas_name
            print(f"  Canvas file        : {canvas_path}  (exists={canvas_path.exists()})")
            if canvas_path.exists():
                ok("Canvas file found")
            else:
                warn(f"Canvas NOT found at expected path — medals will render but canvas will be missing")

    # ------------------------------------------------------------------
    section("9. build_showcase_data() dry run")
    # ------------------------------------------------------------------
    if career_json and country_key:
        try:
            coordinates = load_career_coordinates(career_json)
            payload = build_showcase_data(
                country_key=country_key,
                earned_showcase_names=earned,
                coordinates=coordinates,
                assets_dir=assets_dir,
                tracker_asset_url_prefix='/api/career_assets',
                canvas_filenames=CAREER_CANVAS_FILENAME,
                overlay_filenames=CAREER_OVERLAY_FILENAME,
            )
            ok("build_showcase_data() succeeded")
            print(f"  canvas_url     : {payload.get('canvas_url')}")
            print(f"  overlay        : {payload.get('overlay')!r}")
            print(f"  medals count   : {len(payload.get('medals', []))}")
            if payload.get('medals'):
                print(f"  first medal    : {payload['medals'][0]}")
        except Exception as exc:
            fail(f"build_showcase_data() raised: {exc}")
    else:
        warn("Skipping dry run (missing career_json or country_key)")

    # ------------------------------------------------------------------
    section("Summary")
    # ------------------------------------------------------------------
    print()
    if career_json and showcase_base and country_key:
        ok("Core prerequisites look good — if route still returns 404, check:")
        print("     a) _career_data_dir in routes.py matches this data_dir")
        print("     b) The running server has been restarted after code changes")
        print("     c) Browser JS is not cached (hard-refresh Ctrl+Shift+R)")
    else:
        fail("One or more prerequisites are missing — see [FAIL] lines above")


if __name__ == '__main__':
    main()
