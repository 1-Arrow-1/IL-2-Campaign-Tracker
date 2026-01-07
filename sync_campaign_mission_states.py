diff --git a/sync_campaign_mission_states.py b/sync_campaign_mission_states.py
new file mode 100644
index 0000000000000000000000000000000000000000..0dd4a6f504dbc4290f64de01f3396f047a9a787b
--- /dev/null
+++ b/sync_campaign_mission_states.py
@@ -0,0 +1,320 @@
+#!/usr/bin/env python3
+"""
+Synchronize campaignsstates.txt with on-disk missions.
+
+Removes decoded mission entries that no longer exist on disk and
+regenerates downstream artifacts after updating campaignsstates.txt.
+"""
+
+from __future__ import annotations
+
+import re
+import shutil
+import urllib.parse
+from pathlib import Path
+from typing import Dict, Iterable, List, Set, Tuple
+
+from cleanup_failed_missions import (
+    MissionCleanup,
+    resync_campaign_events_for_campaign,
+    update_completion_state_for_campaign,
+)
+from decode_campaign_usersave1 import main as decode_campaignsstates
+from decode_campaign_usersave1 import parse_campaignsstates
+from utils.il2_paths import (
+    find_campaignsstates_path,
+    read_game_directory,
+    resolve_campaigns_dir,
+)
+
+MISSION_PATTERNS = ("*.Mission*", "*.mission*", "*.msnbin", "*.MSNBIN")
+
+
+def _sort_mission_ids(mission_ids: Iterable[str]) -> List[str]:
+    def sort_key(mission_id: str) -> Tuple[int, int | str, str]:
+        match = re.match(r"^(\d+)", mission_id)
+        if match:
+            return (0, int(match.group(1)), mission_id)
+        return (1, mission_id, mission_id)
+
+    return sorted({str(mission_id) for mission_id in mission_ids}, key=sort_key)
+
+
+def _encode_stats(stats: Dict[str, object]) -> str:
+    if not stats:
+        return ""
+    parts = []
+    for stat_key, stat_val in stats.items():
+        value_str = "" if stat_val is None else str(stat_val)
+        parts.append(f"{stat_key}={value_str}")
+    return urllib.parse.quote("&".join(parts), safe="")
+
+
+def _encode_mission_dict(missions: Dict[str, object], *, is_stats: bool) -> str:
+    if not missions:
+        return ""
+    mission_parts = []
+    for mission_id in _sort_mission_ids(missions.keys()):
+        encoded_id = urllib.parse.quote(str(mission_id), safe="")
+        if is_stats:
+            encoded_data = _encode_stats(missions.get(mission_id, {}))
+        else:
+            raw_value = missions.get(mission_id, "")
+            raw_str = "" if raw_value is None else str(raw_value)
+            encoded_data = urllib.parse.quote(raw_str, safe="")
+        mission_parts.append(f"{encoded_id}={encoded_data}")
+    subval_decoded = "&".join(mission_parts)
+    return urllib.parse.quote(subval_decoded, safe="")
+
+
+def _encode_campaignsstates(campaigns: Dict[str, dict]) -> str:
+    entries = []
+    for campaign_name, params in campaigns.items():
+        if not isinstance(params, dict):
+            continue
+        param_parts = []
+        for key, value in params.items():
+            if key in ("characterStatisticsByFileName", "completedMissionsByFileName"):
+                encoded_value = _encode_mission_dict(
+                    value or {}, is_stats=(key == "characterStatisticsByFileName")
+                )
+                param_parts.append(f"{key}={encoded_value}")
+            else:
+                value_str = "" if value is None else str(value)
+                encoded_value = urllib.parse.quote(value_str, safe="")
+                param_parts.append(f"{key}={encoded_value}")
+        param_string = "&".join(param_parts)
+        encoded_value = urllib.parse.quote(param_string, safe="")
+        encoded_name = urllib.parse.quote(str(campaign_name), safe="")
+        entries.append(f"campaigns/{encoded_name}={encoded_value}")
+    return "&".join(entries)
+
+
+def _collect_campaign_missions(campaigns_dir: Path) -> Dict[str, Set[str]]:
+    mission_map = {}
+    if not campaigns_dir.exists():
+        return mission_map
+    for folder in campaigns_dir.iterdir():
+        if not folder.is_dir():
+            continue
+        mission_ids = set()
+        for pattern in MISSION_PATTERNS:
+            for mission_file in folder.glob(pattern):
+                mission_ids.add(mission_file.stem)
+        mission_map[folder.name.lower()] = mission_ids
+    return mission_map
+
+
+def _regenerate_reports(affected_campaigns: Set[str]) -> None:
+    if not affected_campaigns:
+        return
+    print("\n" + "=" * 70)
+    print("REGENERATING PDF REPORTS")
+    print("=" * 70)
+    print(f"Regenerating PDFs for {len(affected_campaigns)} campaign(s)...")
+
+    import step3_generate_events
+
+    generator = step3_generate_events.EventGenerator(dry_run=False, show_popups=False)
+
+    for campaign_name in sorted(affected_campaigns):
+        print(f"\n  Processing: {campaign_name}")
+        try:
+            resync_result = resync_campaign_events_for_campaign(campaign_name, generator)
+            events = resync_result["events"]
+            campaign_data = resync_result["campaign_data"]
+            completed_missions = resync_result["completed_missions"]
+            country = resync_result["country"]
+            update_completion_state_for_campaign(campaign_name, campaign_data=campaign_data)
+
+            if events:
+                if country:
+                    generator.update_campaign_info_file(
+                        campaign_name, resync_result["combined_html"]
+                    )
+
+                    if completed_missions and len(completed_missions) > 0:
+                        print("    Regenerating PDF...")
+                        generator.set_mode("pdf")
+                        debriefings_html_pdf, debriefings_pdf = (
+                            generator.generate_debriefings_html(
+                                campaign_name, completed_missions
+                            )
+                        )
+                        events_html_pdf = generator.generate_events_html(
+                            events, country, for_pdf=True
+                        )
+                        if debriefings_html_pdf:
+                            combined_html_pdf = (
+                                debriefings_html_pdf + "\n" + events_html_pdf
+                            )
+                        else:
+                            combined_html_pdf = events_html_pdf
+
+                        cumulative_stats = None
+                        try:
+                            stats = campaign_data.get("characterStatisticsByFileName", {})
+                            if stats:
+                                latest_mission = max(
+                                    stats.keys(),
+                                    key=lambda x: int(x) if x.isdigit() else 0,
+                                )
+                                cumulative_stats = stats.get(latest_mission, {})
+                        except Exception:
+                            pass
+
+                        summary_html = generator.generate_campaign_summary_html(
+                            campaign_name,
+                            events,
+                            debriefings_pdf,
+                            country,
+                            cumulative_stats,
+                            campaign_data,
+                        )
+
+                        if summary_html:
+                            combined_html_pdf += "\n" + summary_html
+
+                        generator.export_campaign_to_pdf(campaign_name, combined_html_pdf)
+                        generator.set_mode("ingame")
+                        print("    ✓ PDF regenerated")
+                    else:
+                        print("    ℹ️  No completed missions - skipping PDF")
+                        pdf_path = Path("reports") / f"{campaign_name}_Report.pdf"
+                        if pdf_path.exists():
+                            try:
+                                pdf_path.unlink()
+                                print(f"    ✓ Removed outdated PDF: {pdf_path.name}")
+                            except Exception as e:
+                                print(f"    ⚠️  Could not remove PDF: {e}")
+                else:
+                    print("    ⚠️  No country metadata found")
+            else:
+                print("    ℹ️  No events generated")
+                try:
+                    if not completed_missions:
+                        print("    ℹ️  No missions left - cleaning up")
+                        pdf_path = Path("reports") / f"{campaign_name}_Report.pdf"
+                        if pdf_path.exists():
+                            try:
+                                pdf_path.unlink()
+                                print(f"    ✓ Removed PDF: {pdf_path.name}")
+                            except Exception as e:
+                                print(f"    ⚠️  Could not remove PDF: {e}")
+
+                        if country:
+                            generator.update_campaign_info_file(campaign_name, "")
+                            print("    ✓ Cleared campaign info file")
+                except Exception as e:
+                    print(f"    ⚠️  Error during cleanup: {e}")
+        except Exception as e:
+            print(f"    ⚠️  Error regenerating for {campaign_name}: {e}")
+
+    print("\n✅ PDF regeneration complete")
+
+
+def sync_campaign_states(states_path: str | None = None) -> bool:
+    base_dir = Path.cwd()
+    game_directory = read_game_directory(base_dir)
+    if states_path is None:
+        states_path_obj = find_campaignsstates_path(game_directory)
+    else:
+        states_path_obj = Path(states_path)
+
+    if not states_path_obj or not states_path_obj.exists():
+        print("❌ campaignsstates.txt not found. Aborting sync.")
+        return False
+
+    campaigns_dir = resolve_campaigns_dir(game_directory)
+    if not campaigns_dir.exists():
+        print(f"⚠️  Campaigns directory not found: {campaigns_dir}")
+        return False
+
+    print(f"Using campaignsstates.txt: {states_path_obj}")
+    print(f"Using campaigns directory: {campaigns_dir}")
+
+    campaigns = parse_campaignsstates(str(states_path_obj))
+    on_disk = _collect_campaign_missions(campaigns_dir)
+
+    affected_campaigns: Set[str] = set()
+    removed_summary = []
+    missing_state_summary = []
+
+    for campaign_name, params in campaigns.items():
+        if not isinstance(params, dict):
+            continue
+        folder_key = campaign_name.lower()
+        on_disk_missions = on_disk.get(folder_key)
+        if on_disk_missions is None:
+            print(f"⚠️  Campaign folder missing on disk: {campaign_name}")
+            continue
+
+        completed = params.get("completedMissionsByFileName", {}) or {}
+        stats = params.get("characterStatisticsByFileName", {}) or {}
+        decoded_ids = set(completed.keys()) | set(stats.keys())
+
+        missing_on_disk = decoded_ids - on_disk_missions
+        missing_in_state = on_disk_missions - decoded_ids
+
+        if missing_on_disk:
+            for mission_id in missing_on_disk:
+                completed.pop(mission_id, None)
+                stats.pop(mission_id, None)
+            removed_summary.append((campaign_name, sorted(missing_on_disk)))
+            affected_campaigns.add(campaign_name)
+
+        if missing_in_state:
+            missing_state_summary.append((campaign_name, sorted(missing_in_state)))
+
+        params["completedMissionsByFileName"] = completed
+        params["characterStatisticsByFileName"] = stats
+
+    if not removed_summary:
+        print("✓ No missing missions detected; no updates required.")
+        if missing_state_summary:
+            print("\nMissions present on disk but missing in state (left unchanged):")
+            for campaign_name, mission_ids in missing_state_summary:
+                print(f"  • {campaign_name}: {', '.join(mission_ids)}")
+        return False
+
+    cleanup_tool = MissionCleanup(campaignstates_path=str(states_path_obj))
+    backup_path = cleanup_tool.create_backup()
+    if not backup_path:
+        print("❌ Backup failed; aborting sync.")
+        return False
+
+    encoded = _encode_campaignsstates(campaigns)
+    states_path_obj.write_text(encoded, encoding="utf-8")
+    print("✓ campaignsstates.txt updated")
+
+    print("\nSUMMARY")
+    print("=" * 70)
+    for campaign_name, mission_ids in removed_summary:
+        print(
+            f"Removed {len(mission_ids)} missing mission(s) from {campaign_name}: "
+            f"{', '.join(mission_ids)}"
+        )
+    if missing_state_summary:
+        print("\nMissions present on disk but missing in state (left unchanged):")
+        for campaign_name, mission_ids in missing_state_summary:
+            print(f"  • {campaign_name}: {', '.join(mission_ids)}")
+
+    print("\nRe-decoding campaignsstates.txt to update campaigns_decoded.json...")
+    try:
+        local_copy = base_dir / "campaignsstates.txt"
+        shutil.copy2(states_path_obj, local_copy)
+        if decode_campaignsstates():
+            print("✓ campaigns_decoded.json successfully regenerated.")
+        else:
+            print("⚠️  Decoder reported failure; campaigns_decoded.json may be outdated.")
+    except Exception as e:
+        print(f"⚠️  Could not re-decode campaigns_decoded.json: {e}")
+
+    _regenerate_reports(affected_campaigns)
+
+    return True
+
+
+if __name__ == "__main__":
+    success = sync_campaign_states()
+    raise SystemExit(0 if success else 1)
