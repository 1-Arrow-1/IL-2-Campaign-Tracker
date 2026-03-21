"""
test_delayed_kill.py
--------------------
Tests for the "delayed kill" (AID:-1 with last-damager) attribution logic
added to il2_mission_debrief.MissionDebriefParser._resolve_indirect_kill().

Scenarios covered
-----------------
1. Direct kill              – AType:3 AID=player  → credited (existing behaviour)
2. Delayed kill             – AType:3 AID=-1, player was last damager within window → credited
3. No damage               – AType:3 AID=-1, no hits on target → NOT credited
4. Other last damager      – AType:3 AID=-1, non-player was last to hit and out-damaged player → NOT credited
5. Time window exceeded    – AType:3 AID=-1, player was last damager but too long ago → NOT credited
6. Proportional fallback   – AType:3 AID=-1, player ≥80 % damage but NOT last damager → credited
7. No double-count         – two AType:3 events for same TID → credited exactly once
"""

import sys
import os
import tempfile
import unittest
from pathlib import Path

# Ensure project root is on sys.path so il2_mission_debrief can be imported
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import il2_mission_debrief
from il2_mission_debrief import _DELAYED_KILL_MAX_TICKS


# ---------------------------------------------------------------------------
# Minimal mission-log line templates
# ---------------------------------------------------------------------------
# Player: PLID=100 (aircraft entity), PID=101 (pilot entity), ISPL:1
# Other attacker: AID=999
# Target aircraft: ID=200, Spitfire Mk.VB (Air category)
# Target BotPilot: ID=201, BotPilot (Excluded by category)

_PLAYER_AID   = 100
_PLAYER_PID   = 101
_OTHER_AID    = 999
_TARGET_TID   = 200
_BOTPILOT_TID = 201

_HDR = (
    "T:0 AType:0 GDate:1941.9.27 GTime:7:00:00 "
    "MFile:missions/test.mission"
)
_PLAYER_LINE = (
    "T:10 AType:10 PLID:{plid} PID:{pid} BUL:0 SH:0 BOMB:0 RCT:0 "
    "(0.000,0.000,0.000) IDS:aaaaaaaa-0000-0000-0000-000000000000 "
    "LOGIN:bbbbbbbb-0000-0000-0000-000000000000 "
    "NAME:TestPilot TYPE:Bf 109 F-2 COUNTRY:201 FORM:0 FIELD:0 "
    "INAIR:0 PARENT:-1 ISPL:1 ISTSTART:0 PAYLOAD:0 FUEL:1.0 SKIN: WM:0"
).format(plid=_PLAYER_AID, pid=_PLAYER_PID)

_TARGET_SPAWN = (
    "T:{t} AType:12 ID:{id} TYPE:Spitfire Mk.VB COUNTRY:102 "
    "NAME:Target PID:-1 POS(0.000,2000.000,0.000)"
)
_BOTPILOT_SPAWN = (
    "T:{t} AType:12 ID:{id} TYPE:BotPilot_LaGG3_RAF43 COUNTRY:102 "
    "NAME:BotPilot PID:{pid} POS(0.000,2000.000,0.000)"
)
_DAMAGE = (
    "T:{t} AType:2 DMG:{dmg:.3f} AID:{aid} TID:{tid} "
    "POS(0.000,2000.000,0.000)"
)
_KILL = (
    "T:{t} AType:3 AID:{aid} TID:{tid} POS(0.000,1800.000,0.000)"
)


def _build_report(*lines):
    """Return a list of mission-log lines (header + player + supplied lines)."""
    return [_HDR, _PLAYER_LINE] + list(lines)


def _parse(lines):
    """Write *lines* to a temp file, parse, and return MissionStats."""
    content = "\n".join(lines) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", encoding="utf-8", delete=False
    ) as fh:
        fh.write(content)
        tmp = fh.name
    try:
        parser = il2_mission_debrief.MissionDebriefParser(tmp, verbose=False)
        parser.parse()
        return parser.stats
    finally:
        os.unlink(tmp)


def _air_kills(stats):
    """Count kills that are not BotPilot/BotGunner (mirrors to_json filtering)."""
    return sum(
        1 for k in stats.kills
        if not any(x in k.type.lower() for x in ["botpilot", "botgunner"])
    )


# ---------------------------------------------------------------------------
class TestDelayedKill(unittest.TestCase):

    # ------------------------------------------------------------------
    def test_direct_kill_credited(self):
        """AType:3 AID=player directly credits the kill."""
        lines = _build_report(
            _TARGET_SPAWN.format(t=100, id=_TARGET_TID),
            _DAMAGE.format(t=200, dmg=0.5, aid=_PLAYER_AID, tid=_TARGET_TID),
            _KILL.format(t=300, aid=_PLAYER_AID, tid=_TARGET_TID),
        )
        stats = _parse(lines)
        self.assertEqual(_air_kills(stats), 1, "Direct kill must be credited")

    # ------------------------------------------------------------------
    def test_delayed_kill_credited_within_window(self):
        """AType:3 AID:-1, player was last damager within 300 s → credited."""
        # last damage at T=1000, kill at T=2000 → gap = 1000 ticks = 20 s < 300 s
        lines = _build_report(
            _TARGET_SPAWN.format(t=100, id=_TARGET_TID),
            _DAMAGE.format(t=1000, dmg=0.5, aid=_PLAYER_AID, tid=_TARGET_TID),
            _KILL.format(t=2000, aid=-1, tid=_TARGET_TID),
        )
        stats = _parse(lines)
        self.assertEqual(
            _air_kills(stats), 1,
            "Delayed kill within time window must be credited",
        )

    # ------------------------------------------------------------------
    def test_no_damage_no_credit(self):
        """AType:3 AID:-1 with zero damage history → NOT credited."""
        lines = _build_report(
            _TARGET_SPAWN.format(t=100, id=_TARGET_TID),
            _KILL.format(t=2000, aid=-1, tid=_TARGET_TID),
        )
        stats = _parse(lines)
        self.assertEqual(
            _air_kills(stats), 0,
            "No damage recorded → kill must not be credited",
        )

    # ------------------------------------------------------------------
    def test_other_last_damager_no_credit(self):
        """AType:3 AID:-1, a non-player was the last to hit and did more damage → NOT credited."""
        lines = _build_report(
            _TARGET_SPAWN.format(t=100, id=_TARGET_TID),
            # Player hits first
            _DAMAGE.format(t=1000, dmg=0.1, aid=_PLAYER_AID, tid=_TARGET_TID),
            # Other attacker hits LAST
            _DAMAGE.format(t=1500, dmg=0.2, aid=_OTHER_AID,  tid=_TARGET_TID),
            _KILL.format(t=2000, aid=-1, tid=_TARGET_TID),
        )
        stats = _parse(lines)
        self.assertEqual(
            _air_kills(stats), 0,
            "Non-player out-damaged player → kill must not be credited",
        )

    # ------------------------------------------------------------------
    def test_dominant_player_damage_vs_multiple_ai_credited(self):
        """Player damage beating all AI attackers combined and individually must credit the kill."""
        lines = _build_report(
            _TARGET_SPAWN.format(t=100, id=_TARGET_TID),
            _DAMAGE.format(t=1000, dmg=0.171, aid=_PLAYER_AID, tid=_TARGET_TID),
            _DAMAGE.format(t=1100, dmg=0.033, aid=201, tid=_TARGET_TID),
            _DAMAGE.format(t=1200, dmg=0.074, aid=202, tid=_TARGET_TID),
            _DAMAGE.format(t=1300, dmg=0.006, aid=203, tid=_TARGET_TID),
            _DAMAGE.format(t=1400, dmg=0.012, aid=204, tid=_TARGET_TID),
            _DAMAGE.format(t=1500, dmg=0.004, aid=205, tid=_TARGET_TID),
            _DAMAGE.format(t=2000, dmg=0.697, aid=-1, tid=_TARGET_TID),
            _KILL.format(t=2000, aid=-1, tid=_TARGET_TID),
        )
        stats = _parse(lines)
        self.assertEqual(
            _air_kills(stats), 1,
            "Player damage dominating all AI follow-up damage should credit the kill",
        )

    # ------------------------------------------------------------------
    def test_delayed_kill_outside_time_window_no_credit(self):
        """AType:3 AID:-1, player was last damager but gap > 300 s → NOT credited.

        The other attacker does the majority of damage (80 %+), so the
        proportional-damage fallback also fails and the kill is not awarded.
        Player delivers only a small finishing hit (< 20 % damage) to remain the
        *last* damager, but the time gap exceeds _DELAYED_KILL_MAX_TICKS.
        """
        # 300 s = 15 000 ticks; gap = 15 001 ticks (just over the window)
        other_damage_tick  = 500
        player_damage_tick = 1000           # player is last damager …
        destroy_tick       = player_damage_tick + _DELAYED_KILL_MAX_TICKS + 1

        lines = _build_report(
            _TARGET_SPAWN.format(t=100, id=_TARGET_TID),
            # Other attacker does 85 % of total damage
            _DAMAGE.format(t=other_damage_tick,  dmg=0.85, aid=_OTHER_AID,   tid=_TARGET_TID),
            # Player does the remaining 15 % (< 80 %) — and is the last damager
            _DAMAGE.format(t=player_damage_tick, dmg=0.15, aid=_PLAYER_AID,  tid=_TARGET_TID),
            _KILL.format(t=destroy_tick, aid=-1, tid=_TARGET_TID),
        )
        stats = _parse(lines)
        self.assertEqual(
            _air_kills(stats), 0,
            "Gap exceeds time window and player < 80 % damage → kill must not be credited",
        )

    # ------------------------------------------------------------------
    def test_proportional_fallback_credited(self):
        """Player ≥80 % damage, non-player was last damager → credited via fallback."""
        # Player does 90% damage, other attacker does 10% and hits LAST
        lines = _build_report(
            _TARGET_SPAWN.format(t=100, id=_TARGET_TID),
            _DAMAGE.format(t=1000, dmg=0.9, aid=_PLAYER_AID, tid=_TARGET_TID),
            _DAMAGE.format(t=1001, dmg=0.1, aid=_OTHER_AID,  tid=_TARGET_TID),
            _KILL.format(t=2000, aid=-1, tid=_TARGET_TID),
        )
        stats = _parse(lines)
        self.assertEqual(
            _air_kills(stats), 1,
            "Player ≥80 % damage → proportional fallback must credit the kill",
        )

    # ------------------------------------------------------------------
    def test_no_double_count_multiple_atype3(self):
        """Two AType:3 events for the same TID → credited exactly once."""
        lines = _build_report(
            _TARGET_SPAWN.format(t=100, id=_TARGET_TID),
            _DAMAGE.format(t=1000, dmg=0.5, aid=_PLAYER_AID, tid=_TARGET_TID),
            _KILL.format(t=2000, aid=-1, tid=_TARGET_TID),
            _KILL.format(t=2001, aid=-1, tid=_TARGET_TID),  # duplicate
        )
        stats = _parse(lines)
        self.assertEqual(
            _air_kills(stats), 1,
            "Duplicate AType:3 for same TID must not be counted twice",
        )

    # ------------------------------------------------------------------
    def test_botpilot_excluded_from_count(self):
        """BotPilot TID killed with AID=-1 must not inflate the kill count."""
        lines = _build_report(
            _TARGET_SPAWN.format(t=100, id=_TARGET_TID),
            _BOTPILOT_SPAWN.format(t=100, id=_BOTPILOT_TID, pid=_TARGET_TID),
            _DAMAGE.format(t=1000, dmg=0.5, aid=_PLAYER_AID, tid=_TARGET_TID),
            _KILL.format(t=2000, aid=-1, tid=_TARGET_TID),
            _KILL.format(t=2000, aid=-1, tid=_BOTPILOT_TID),
        )
        stats = _parse(lines)
        self.assertEqual(
            _air_kills(stats), 1,
            "BotPilot kill must be excluded from the kill count",
        )

    # ------------------------------------------------------------------
    def test_real_mission_report_delayed_kill(self):
        """
        Regression: TID:1025023 (Spitfire Mk.VB) in the real mission report
        missionReport(2026-01-27_21-47-54)[0].txt must be credited as a
        delayed kill (player last damaged it at T=40743, AType:3 at T=43058).
        """
        report = (
            ROOT
            / "missionReport(2026-01-27_21-47-54)[0].txt"
        )
        if not report.exists():
            self.skipTest(f"Real mission report not found: {report}")

        parser = il2_mission_debrief.MissionDebriefParser(report, verbose=False)
        parser.parse()

        credited_tids = {k.id for k in parser.stats.kills}
        self.assertIn(
            1025023,
            credited_tids,
            "TID:1025023 (Spitfire 'Yellow 2') must be credited as a delayed kill",
        )


if __name__ == "__main__":
    unittest.main()
