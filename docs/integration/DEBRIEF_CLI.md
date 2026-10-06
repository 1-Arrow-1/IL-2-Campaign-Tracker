# il2_debrief: mission log analyser for other programs

`il2_debrief.exe` reads one IL-2 Great Battles mission log and writes what happened as a JSON file. It uses the same parser as IL-2 Campaign Tracker, packaged as a standalone program. Use it when your program needs facts from a log: kills, damage taken, bailouts, how each AI aircraft was lost, and the pilot's final state.

It runs headless. It needs no Python install, no tracker GUI, no running server and no campaign database. It is analysis only: it does not write stories. See [STORY_GUARDRAILS.md](STORY_GUARDRAILS.md) for turning its output into a fact-based narrative.

Contents:

1. [Files to ship](#1-files-to-ship)
2. [Calling it](#2-calling-it)
3. [Which log to pass](#3-which-log-to-pass)
4. [Output reference](#4-output-reference)
5. [How the facts are determined](#5-how-the-facts-are-determined)
6. [Known limitations](#6-known-limitations)
7. [Versioning](#7-versioning)
8. [Licence](#8-licence)

## 1. Files to ship

| File | Required | Purpose |
|------|----------|---------|
| `il2_debrief.exe` | yes | The analyser, about 9 MB. Windows x64. |
| `mlg2txt.exe` | only for `.mlg` input | Converts the game's binary `.mlg` logs to text. Must sit in the same folder as `il2_debrief.exe`, or be passed with `--mlg2txt`. Built unmodified from [Murleen/mlg2txt](https://github.com/Murleen/mlg2txt) by Ian Caulfield, MIT licence. |
| `LICENSE` | yes | GPL-3.0, covering `il2_debrief.exe`. |
| `LICENSE-mlg2txt` | with `mlg2txt.exe` | MIT licence for `mlg2txt.exe`. It must ship whenever `mlg2txt.exe` does. |
| `object_categories.yaml` | no | Classifies every game object as Air, Ground, Naval and so on. A copy is built into the exe. Put one next to the exe only to override it. |

[DebriefClient.java](DebriefClient.java) is a dependency-free Java 11+ client you can copy.

## 2. Calling it

```
il2_debrief.exe <log> [<log> ...] --out <result.json> [--mlg2txt <path>] [--pretty] [--verbose]
```

| Argument | Meaning |
|----------|---------|
| `<log>` | Either **one** `.mlg` file, or the `.txt` part(s) of **one** mission. Parts are merged in `[0]`, `[1]`, `[2]` order whatever order you pass them in. |
| `--out` | Where to write the result. Defaults to `<log name>.events.json` next to the log. Always pass it: the default would write into the game folder. |
| `--mlg2txt` | Path to `mlg2txt.exe` if it is not next to `il2_debrief.exe`. |
| `--pretty` | Indent the JSON. Off by default. |
| `--verbose` | Write parser diagnostics to stderr. |

### Contract

- **stdout** carries exactly one line of JSON, and nothing else:
  - success: `{"ok": true, "output": "<absolute path>", "schema_version": 1}`
  - failure: `{"ok": false, "error_code": "<code>", "error": "<message>"}`
- **stderr** carries diagnostics only. Discard it or log it, but drain or redirect it so the pipe can't fill.
- **The output file is written atomically.** It is written to a `.tmp` file and then renamed, so you never read a half-written file. It is not written at all on failure.
- **Speed:** under a second for a typical log, including process start-up.

### Exit codes

| Exit | `error_code` | Meaning |
|------|--------------|---------|
| 0 | | Success. |
| 2 | `input_not_found`, `bad_input` | A file is missing, the input types are mixed, or more than one `.mlg` was passed. |
| 3 | `mlg2txt_not_found`, `mlg_conversion_failed` | `.mlg` input, but `mlg2txt.exe` is missing or failed. |
| 4 | `parse_failed` | The log could not be parsed. |
| 5 | `no_player` | The log has no player aircraft (no `ISPL:1` line). Usually the wrong file, or a log cut off before the player spawned. |

## 3. Which log to pass

The game writes one binary log per mission to `<IL-2 install>\data\FlightLogs\missionReport(<date>_<time>).mlg`. That is the most reliable input, and it is what the tracker itself uses.

If the player has `mission_text_log = 1` in `startup.cfg`, the game also writes text logs to `data\` as `missionReport(<date>_<time>)[0].txt`, `[1].txt`, and so on. A mission is split across several numbered files. Pass all of them, because passing only `[0]` loses everything after the first split.

To find the log for a PWCG mission, take the newest log whose timestamp falls after the mission was started. The log's internal mission name is not reliable for this.

## 4. Output reference

Top level:

```json
{
  "schema_version": 1,
  "generator": { "name": "IL-2 Campaign Tracker debrief", "version": "3.1.13" },
  "source_files": ["missionReport(2026-03-15_22-33-00)[0].txt"],
  "player": { ... },
  "summary": { ... },
  "squadron_flights": [ ... ],
  "events": [ ... ]
}
```

### 4.1 `player`

```json
{ "id": 2143231, "name": "Arrow_1974", "aircraft": "Bf 109 G-6",
  "spawn_x": 214935.078, "spawn_z": 191442.547, "country": "201" }
```

| Field | Notes |
|-------|-------|
| `name` | The **game login name**, not the campaign pilot's name, and only up to its first space. Use PWCG's pilot name instead. |
| `aircraft` | The aircraft display name as the game logs it. |
| `country` | The game's country code as a string: `101` USSR, `102` Great Britain, `103` USA, `201` Germany, `202` Italy. Compare it with `squadron_flights[].country` to tell friend from foe. |
| `spawn_x`, `spawn_z` | Map coordinates in metres: x is east, z is north. |

### 4.2 `summary`

```json
{ "air_kills": 4, "air_kills_flying": 4, "air_kills_parked": 0,
  "ground_kills": 0, "naval_kills": 0, "flight_duration": "00:13:24",
  "wounded": false, "aircraft_damage": 100.0, "pilot_damage": 0.0,
  "landed": false, "crashed": false, "final_state": "Bailout (Survived)",
  "mission_start_time": "06:17", "combat_metrics": { ... },
  "total_damage_taken": 0.0 }
```

| Field | Notes |
|-------|-------|
| `air_kills` | `air_kills_flying + air_kills_parked`. Use `air_kills_flying` as the aerial victory count. Parked aircraft destroyed on the ground count only toward `air_kills_parked`. |
| `ground_kills` | Ground vehicles and buildings. Balloon kills appear in `events` but in no summary count. |
| `flight_duration` | `HH:MM:SS` from takeoff to landing, or to the last event. `"N/A"` if the player never took off. |
| `wounded` | True once total pilot damage reaches 5%. |
| `aircraft_damage`, `pilot_damage` | Cumulative damage in percent, roughly 0 to 100. |
| `final_state` | **The authoritative outcome.** Prefer it over `landed` and `wounded`, which can disagree with it. For example, a pilot killed after touching down has `landed: true` and `final_state: "KIA"`. |
| `mission_start_time` | In-game clock time at mission start (`HH:MM`). Event `time` values are offsets from this. |
| `combat_metrics` | Ammunition and ordnance statistics. Every block has a `status`; only `"ok"` means the numbers are real. A `status` beginning `n/a_` means unlimited ammo, no such weapon, or nothing fired. |
| `crashed` | **Always `false`.** Reserved; don't use it. |
| `total_damage_taken` | **Always 0.** Deprecated. |

`final_state` takes one of these values:

| Value | Meaning |
|-------|---------|
| `Landed` | Landed normally on friendly or neutral ground. |
| `Landed (Wounded)` | Landed with at least 5% pilot damage. |
| `Landed (Hard Landing)`, `Landed (Hard Landing, Wounded)` | Took self-inflicted or unattributed damage in the 60 seconds before landing, outside combat and near the ground. |
| `Bailout (Survived)`, `Bailout (Survived, Wounded)` | Bailed out and either touched down in friendly or unknown territory, or the mission ended mid-descent over friendly territory. |
| `MIA (Captured)` | Landed or touched down in enemy territory. |
| `MIA (Likely Captured)` | Bailed out over enemy territory and the mission ended before touchdown. |
| `MIA (Unknown)` | Bailed out and the mission ended before touchdown, over territory that could not be determined. |
| `KIA` | Pilot damage reached 99% or more. |
| `Alive` | No landing, bailout or death was recorded. Usually the mission was ended in the air, or the log was cut short. |

Territory comes from the front-line polygons in the log, so it is only as accurate as the mission's front-line data.

### 4.3 `events`

The player's own timeline, sorted by `time`. `time` is `HH:MM:SS` of in-game time since the log started. Add it to `summary.mission_start_time` for the clock time.

```json
{"time": "00:00:00", "type": "Takeoff", "altitude": null, "time_raw": 30}
{"time": "00:06:42", "type": "Kill", "target": "Li-2", "category": "Air", "is_static": false, "altitude": 1246}
{"time": "00:11:21", "type": "Damage Taken", "target": null, "attacker_unknown": true, "damage": "61.4% aircraft", "altitude": 680, "time_raw": "00:11"}
{"time": "00:13:24", "type": "Pilot Touchdown", "altitude": null, "time_raw": 40240}
```

| `type` | Fields | Notes |
|--------|--------|-------|
| `Takeoff` | `altitude` | |
| `Landing` | `altitude`, `hard_landing` | `hard_landing: true` when the landing damaged the aircraft. |
| `Pilot Touchdown` | `altitude` | The parachute reached the ground after a bailout. |
| `Kill` | `target`, `category`, `is_static`, `altitude`, `delayed` | `target` is the object type, e.g. `"Yak-1 ser.69"`. `category` is `Air`, `Ground`, `Building`, `Naval`, `Balloon` or `Unknown`. `is_static: true` means a parked aircraft. `delayed: true` means credited by the rules in section 5 rather than by a direct game kill record. `altitude` is in metres and is left out for delayed air kills, because the crash-site altitude says nothing about the fight. |
| `Damage Taken` | `target`, `attacker_unknown`, `damage`, `altitude` | One event per minute, with damage summed. **`target` is the attacker's type**, e.g. `"Yak-1 ser.69"`, despite the name. `target: null` with `attacker_unknown: true` means the game logged no attacker: fire, crash impact, collision or other environmental damage. `damage` is text such as `"12.0% aircraft"`, `"5.0% pilot"` or `"4.2% aircraft, 19.2% pilot"`. |
| `Landing Damage` | as `Damage Taken`, plus `original_target` | Damage reclassified as caused by the landing. |

There is **no `Bailout` event**. A bailout shows up in `final_state` and as a `Pilot Touchdown` event when the parachute lands before the mission ends. There is also no `Crash` event.

**Don't use `time_raw`.** It is a tick count on some events and an `"HH:MM"` string on others.

`altitude` may be `null` on any event.

### 4.4 `squadron_flights`

One entry for **every AI aircraft in the mission that has a named pilot, on both sides**. Despite the name, it is not limited to the player's squadron. Enemy aircraft are included: compare `country` with `player.country` to separate them. The player's own aircraft is excluded.

```json
{"name": "Yury Martynov,101408,1", "aircraft_type": "Li-2", "country": "101",
 "air_kills": 0, "air_kills_parked": 0, "ground_kills": 0,
 "outcome": "shot_down", "shot_down_by_type": "Bf 109 G-6",
 "kill_cause": "shot_down", "spawn_tick": 8700}
```

| Field | Notes |
|-------|-------|
| `name` | The pilot name from the log. Some names carry trailing comma-separated codes the game adds (`"Yury Martynov,101408,1"`). **Match on the part before the first comma.** |
| `aircraft_type` | The aircraft display name. |
| `air_kills`, `air_kills_parked`, `ground_kills` | Kills where this aircraft was the direct attacker in the log. Kills that burned or crashed later are not credited to AI pilots. |
| `outcome` | `survived`; `bailed_survived` (aircraft destroyed, pilot landed by parachute); `shot_down` (aircraft destroyed, pilot not seen to land); `killed` (the pilot themselves was killed). `shot_down` covers **any** loss of the aircraft, including collisions and crashes. Use `kill_cause` for how it happened. |
| `kill_cause` | Present only when the aircraft was destroyed. See the table below. |
| `shot_down_by_type` | The type of whatever the game logged as destroying it. It can be a friendly aircraft (collision, friendly fire) or a flak gun. |
| `spawn_tick` | Present only for aircraft that spawned without the usual pilot record, typically pre-placed or late-spawned AI. A larger number means a later spawn, at 50 ticks per second. |

`kill_cause` values. These are the guardrails for the narrative:

| Value | How it is determined | Say | Never say |
|-------|----------------------|-----|-----------|
| `shot_down` | Destroyed by an enemy aircraft that survived the moment. | shot down by enemy fighters | |
| `collision_enemy` | Destroyed by an enemy aircraft, and **both** were destroyed within 1 second. | collided with an enemy aircraft | shot down |
| `collision_friendly` | Destroyed by a same-side aircraft with both destroyed within 1 second, **or** no attacker was logged and it caught fire within 0.1 seconds and 50 m of another AI aircraft (of either side) catching fire. | mid-air collision, accident | any enemy action |
| `friendly_fire` | Destroyed by a same-side aircraft that survived. | friendly fire, accident | enemy action |
| `killed_by_aa` | Destroyed by a ground or naval unit. | brought down by flak or AA | shot down by a fighter |
| `crashed_combat` | No attacker logged, but it had taken combat damage earlier. | damaged in combat, later crashed or burned | shot down outright |
| `crashed` | No attacker logged and no combat damage. | engine failure, accident, unknown cause | combat loss |

## 5. How the facts are determined

The game logs a destruction with an attacker ID. When that ID is the player, the kill is direct and certain. When the attacker is missing (`AID:-1`), which is typical for an aircraft that burns or glides in after being hit, the kill goes to the player if **any** of these hold, in order:

1. The player was the last aircraft to damage it, within 600 seconds before it was destroyed.
2. The player dealt 80% or more of all recorded damage to it.
3. The player was the only attacker, aircraft or ground unit, that ever damaged it.
4. The player's damage exceeded all other attackers' damage combined.

Kills credited this way are marked `"delayed": true`.

After the log has been read, any destroyed object where the player dealt at least 80% of the damage is also credited, even if another aircraft got the final hit. These kills are **not** marked `delayed`.

How reliable the facts are:

| Fact | Reliability |
|------|-------------|
| Direct kills, takeoff, landing, bailout, KIA, AI aircraft losses with an attacker | As reliable as the game log. |
| Collision detection | Strong when both aircraft are destroyed. A collision where one aircraft survives looks like `shot_down` or `friendly_fire`. |
| Delayed kills | Heuristic. Generally correct, but shared kills may differ from what the game's own scoring credits. |
| Territory (captured or MIA) | Depends on the mission's front-line data. |

## 6. Known limitations

- **The player's own loss has no `kill_cause`.** `kill_cause` exists only for AI aircraft. For the player, use the `Damage Taken` events, their attacker types and timing, and `final_state`. If the player collides with another aircraft, the evidence is that aircraft's `kill_cause`, a large `Damage Taken` with `attacker_unknown: true` at the same time, or both.
- **The player's name is the login name**, as noted in section 4.1.
- **No PWCG test yet.** The parser has been used with IL-2 career missions and single-player campaigns. PWCG builds its own missions, and how it names AI pilots and spawns flights may differ. Expect name matching in particular to need checking against real PWCG logs.
- **Unlimited ammo** makes the ammunition numbers in `combat_metrics` unavailable (`status: "n/a_unlimited_ammo"`).
- **Times are in-game time** since the log started, so time compression is already included.

## 7. Versioning

`schema_version` (currently `1`) increases whenever a field is renamed, removed or changes meaning. New fields may be added without a bump, so ignore fields you don't recognise. Refuse or warn on a `schema_version` higher than the one you were built for. `generator.version` is the tracker release the analyser was built from; use it in bug reports.

## 8. Licence

IL-2 Campaign Tracker, including this analyser, is licensed under the GNU GPL v3.

Running `il2_debrief.exe` as a separate program and reading its JSON output is arm's-length communication between two programs, so it does not bring the calling program under the GPL. Shipping `il2_debrief.exe` with your mod is conveying it, so include the licence and point to the source.

Copying or translating the parser's code into your own program would make that program a derivative work, which the GPL then covers.

`mlg2txt.exe` is separate work by Ian Caulfield under the MIT licence ([Murleen/mlg2txt](https://github.com/Murleen/mlg2txt)). If you redistribute it, include `LICENSE-mlg2txt`.
