"""
test_player_collision.py
------------------------
Tests for player collisions and self-destruction in il2_mission_debrief.

IL-2 logs a collision involving the player as the player's aircraft
destroying the other one, and can log the player's aircraft as destroying
itself. Neither may count as a kill.

Scenarios covered
-----------------
1. Enemy collision       – player "destroys" X, player destroyed by AID:-1 within 1 s → Collision, not a kill
2. Friendly collision    – same, X on the player's side → Collision with friendly=True
3. Self-destroyed player – player destroyed by itself within 1 s → still a collision
4. Head-on gunfight      – player destroys X, X's fire kills the player within 1 s → genuine kill
5. Earlier kill          – player destroys X long before dying → genuine kill
6. Self-kill             – AType:3 AID=player TID=player → never a kill
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import il2_mission_debrief

_PLAYER_AID = 100
_PLAYER_PID = 101
_TARGET_TID = 200

_HDR = "T:0 AType:0 GDate:1941.9.27 GTime:7:00:00 MFile:missions/test.mission"
_PLAYER_LINE = (
    "T:10 AType:10 PLID:{plid} PID:{pid} BUL:0 SH:0 BOMB:0 RCT:0 "
    "(0.000,0.000,0.000) IDS:aaaaaaaa-0000-0000-0000-000000000000 "
    "LOGIN:bbbbbbbb-0000-0000-0000-000000000000 "
    "NAME:TestPilot TYPE:Bf 109 F-2 COUNTRY:201 FORM:0 FIELD:0 "
    "INAIR:0 PARENT:-1 ISPL:1 ISTSTART:0 PAYLOAD:0 FUEL:1.0 SKIN: WM:0"
).format(plid=_PLAYER_AID, pid=_PLAYER_PID)
# Real logs register the player's aircraft with an AType:12 line as well.
_PLAYER_AIRCRAFT = (
    "T:10 AType:12 ID:{plid} TYPE:Bf 109 F-2 COUNTRY:201 "
    "NAME:Test Pilot PID:-1 POS(0.000,2000.000,0.000)"
).format(plid=_PLAYER_AID)
_SPAWN = (
    "T:{t} AType:12 ID:{id} TYPE:{type} COUNTRY:{country} "
    "NAME:Target PID:-1 POS(0.000,2000.000,0.000)"
)
_DAMAGE = "T:{t} AType:2 DMG:{dmg:.3f} AID:{aid} TID:{tid} POS(0.000,2000.000,0.000)"
_DESTROY = "T:{t} AType:3 AID:{aid} TID:{tid} POS(0.000,1800.000,0.000)"


def _enemy():
    return _SPAWN.format(t=100, id=_TARGET_TID, type="Spitfire Mk.VB", country=102)


def _friendly():
    return _SPAWN.format(t=100, id=_TARGET_TID, type="Bf 109 F-2", country=201)


def _parse_to_json(*lines):
    """Parse a synthetic log and return (stats, to_json() output)."""
    content = "\n".join([_HDR, _PLAYER_AIRCRAFT, _PLAYER_LINE, *lines]) + "\n"
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "missionReport.txt"
        log.write_text(content, encoding="utf-8")
        parser = il2_mission_debrief.MissionDebriefParser(str(log), verbose=False)
        stats = parser.parse()
        out = Path(tmp) / "out.json"
        parser.to_json(out)
        return stats, json.loads(out.read_text(encoding="utf-8"))


def _events(data, event_type):
    return [e for e in data["events"] if e["type"] == event_type]


class TestPlayerCollision(unittest.TestCase):

    def test_enemy_collision_is_not_a_kill(self):
        _, data = _parse_to_json(
            _enemy(),
            _DAMAGE.format(t=4000, dmg=0.9, aid=_PLAYER_AID, tid=_TARGET_TID),
            _DESTROY.format(t=4000, aid=_PLAYER_AID, tid=_TARGET_TID),
            _DESTROY.format(t=4010, aid=-1, tid=_PLAYER_AID),
        )
        self.assertEqual(data["summary"]["air_kills"], 0)
        self.assertEqual(_events(data, "Kill"), [])
        collisions = _events(data, "Collision")
        self.assertEqual(len(collisions), 1)
        self.assertEqual(collisions[0]["target"], "Spitfire Mk.VB")
        self.assertFalse(collisions[0]["friendly"])

    def test_friendly_collision_is_flagged_friendly(self):
        _, data = _parse_to_json(
            _friendly(),
            _DESTROY.format(t=4000, aid=_PLAYER_AID, tid=_TARGET_TID),
            _DESTROY.format(t=4000, aid=-1, tid=_PLAYER_AID),
        )
        self.assertEqual(data["summary"]["air_kills"], 0)
        collisions = _events(data, "Collision")
        self.assertEqual(len(collisions), 1)
        self.assertTrue(collisions[0]["friendly"])

    def test_player_destroyed_by_itself_still_a_collision(self):
        _, data = _parse_to_json(
            _enemy(),
            _DESTROY.format(t=4000, aid=_PLAYER_AID, tid=_TARGET_TID),
            _DESTROY.format(t=4030, aid=_PLAYER_AID, tid=_PLAYER_AID),
        )
        self.assertEqual(data["summary"]["air_kills"], 0)
        self.assertEqual(len(_events(data, "Collision")), 1)

    def test_head_on_gunfight_remains_a_kill(self):
        """Enemy fire kills the player in the same second: the log names the enemy."""
        _, data = _parse_to_json(
            _enemy(),
            _DESTROY.format(t=4000, aid=_PLAYER_AID, tid=_TARGET_TID),
            _DESTROY.format(t=4010, aid=_TARGET_TID, tid=_PLAYER_AID),
        )
        self.assertEqual(data["summary"]["air_kills"], 1)
        self.assertEqual(_events(data, "Collision"), [])

    def test_earlier_kill_remains_a_kill(self):
        _, data = _parse_to_json(
            _enemy(),
            _DESTROY.format(t=1000, aid=_PLAYER_AID, tid=_TARGET_TID),
            _DESTROY.format(t=4000, aid=-1, tid=_PLAYER_AID),
        )
        self.assertEqual(data["summary"]["air_kills"], 1)
        self.assertEqual(_events(data, "Collision"), [])

    def test_player_destroying_itself_is_never_a_kill(self):
        stats, data = _parse_to_json(
            _DAMAGE.format(t=3990, dmg=0.96, aid=_PLAYER_AID, tid=_PLAYER_AID),
            _DESTROY.format(t=4000, aid=_PLAYER_AID, tid=_PLAYER_AID),
        )
        self.assertEqual(data["summary"]["air_kills"], 0)
        self.assertEqual(_events(data, "Kill"), [])
        self.assertTrue(all(k.id not in (_PLAYER_AID, _PLAYER_PID) for k in stats.kills))


if __name__ == "__main__":
    unittest.main()
