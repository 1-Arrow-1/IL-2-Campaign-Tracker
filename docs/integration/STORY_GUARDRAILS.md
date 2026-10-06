# Writing fact-based mission stories from il2_debrief output

This guide covers the second half of the pipeline: turning `il2_debrief` output plus your own campaign context into an after-action story that does not invent facts. It is based on what IL-2 Campaign Tracker does for its own career stories. That includes the mistakes language models actually made there, which the rules below exist to prevent.

The principle: **the model writes prose; it never decides facts.** Every fact is settled before the prompt is built, and the prompt forbids the model from adding to them.

## 1. Two sources of truth

| Source | Authoritative for |
|--------|-------------------|
| `il2_debrief` JSON | What happened in the air: kills, damage, timing, bailout, landing, the pilot's final state, and how each AI aircraft was lost. |
| Your campaign data (PWCG) | Who and why: pilot and squadron names, ranks, mission objective, briefing, date, location, the campaign situation, and awards and promotions. |

When they overlap, decide in code which one wins before writing the prompt. Don't hand the model two conflicting facts and let it choose.

The tracker's rule: the campaign database's casualty status (KIA or MIA) overrides the log's `final_state`, because the game's own career logic made the final call. If PWCG records a pilot's fate, the same reasoning applies.

## 2. Build a compact fact payload

**Don't send the raw JSON to the model.** It is large; a busy mission has dozens of `squadron_flights` entries. The tracker found that sending it whole costs tens of thousands of tokens and makes the model fixate on irrelevant detail.

Pre-process it into a small payload:

1. **Split `squadron_flights` by side.** Entries whose `country` equals `player.country` are your side; the rest are enemies.
2. **Keep only the player's own flight or squadron** from your side. Match names on the part before the first comma (`"Ivan Petrov,101408,1"` becomes `Ivan Petrov`) against PWCG's roster. Drop anyone who doesn't match. Never let unmatched log names into the story.
3. **Drop the uneventful ones.** Keep squadron entries that scored kills or whose `outcome` is not `survived`.
4. **Turn events into short factual lines** with clock times (`summary.mission_start_time` plus the event `time`):
   - `Kill` becomes "Destroyed a Yak-1 ser.69 (air, 1,250 m)". Add "(fell later)" when `delayed` is true, and leave altitude out in that case.
   - `Damage Taken` becomes "Hit by a Yak-1 ser.69: 12% aircraft damage". When `attacker_unknown` is true, write "unattributed damage" and don't name an attacker.
   - Leave out `combat_metrics`, `time_raw`, coordinates and IDs.
5. **Use your names, not the log's.** Use PWCG's pilot name and rank for the player, not `player.name`, which is a login name.

An example payload:

```json
{
  "pilot":    { "rank": "Leutnant", "last_name": "Becker", "squadron": "II./JG 52", "aircraft": "Bf 109 G-6" },
  "mission":  {
    "date": "1943-04-17", "start_time": "06:17", "time_of_day": "dawn", "season": "spring",
    "location": "Kuban", "objective": "Intercept enemy transports",
    "briefing": "<PWCG briefing text>",
    "result": "Bailout (Survived)",
    "air_kills": 4,
    "events": [
      "06:23 Destroyed a Li-2 (air, 1,246 m)",
      "06:28 Hit by unattributed damage: 61% aircraft damage",
      "06:30 Parachute touchdown"
    ]
  },
  "flight_results": [
    { "pilot": "Wilhelm Thieme", "rank": "Unteroffizier", "outcome": "shot_down", "kill_cause": "collision_friendly" }
  ],
  "campaign_progress": { "aerial_victories_before_mission": 11 },
  "post_mission": { "awards": [], "promotion": "" }
}
```

Keep `post_mission` separate from the mission. Awards and promotions happen **after landing**. Mixed into the mission facts, the model reliably narrates them as happening mid-flight.

## 3. Prompt rules

These are adapted from the tracker's prompt. Each one exists because a model broke it. Paste them in and adjust the field names to match your payload.

```text
Write an after-action story for one mission.
Use only the facts in the input JSON. Do not invent victories, losses, injuries,
awards, promotions, locations, units, or people.

People
- Name only people who appear in the input. Do not invent commanders, wingmen,
  adjutants or ground crew by name; use "his flight leader", "the duty officer".
- First mention of the pilot is rank + last name; afterwards last name only.
- Use names exactly as given. Use a rank only if one is supplied for that person.

How aircraft were lost (flight_results[].kill_cause is authoritative)
- shot_down: destroyed by enemy aircraft fire.
- collision_enemy: mid-air collision with an enemy aircraft. Describe a collision,
  NOT a shoot-down.
- collision_friendly: mid-air collision with a friendly aircraft. A tragic accident;
  never enemy action.
- friendly_fire: hit by friendly guns. An accident of war; never enemy action.
- killed_by_aa: brought down by anti-aircraft fire from the ground.
- crashed_combat: damaged in combat, later crashed or burned.
- crashed: lost without enemy involvement (failure, error, unknown).
- Never write "shot down" unless kill_cause is "shot_down".
- outcome "bailed_survived" = parachuted to safety; "killed" = the pilot died;
  "shot_down" = aircraft lost, pilot's fate unknown at the time.

The pilot's own mission
- mission.result is the authoritative outcome. Do not contradict it.
- Damage marked unattributed has no known attacker; do not invent one.
- Kills marked "(fell later)" went down after the engagement; do not describe
  them exploding under the pilot's guns.
- The pilot's victory total after this mission is
  aerial_victories_before_mission + mission.air_kills. Never estimate it.

Order and timing
- Tell the story chronologically: before take-off, outbound, action, return,
  then post_mission.
- post_mission awards and promotions happen after landing. Never mention them
  before the pilot has landed. If post_mission is empty, mention no award or promotion.
- Use time_of_day and season for atmosphere if present; never invent weather
  or time that contradicts them.

Style
- Third person, past tense, historical narrative, not a debrief report.
- Weave facts into prose; no lists, no stat dumps, no internal IDs.
- Use the pilot's own air force's terminology (Rotte/Schwarm for Luftwaffe,
  Para/Zveno for VVS, Element/Flight for RAF/USAAF).
- Return JSON: {"title": "...", "story_text": "..."}.
```

## 4. Check the output in code

Don't trust the model to have followed the rules.

What the tracker does after every generation:

- **Report style.** It rejects text that reads like a debrief: bullet points, `Label: value` lines, several numbers crammed into one sentence.
- **Truncation and reasoning leaks.** It rejects text that ends mid-sentence or contains the model thinking aloud. It retries with a simpler plain-text prompt; if that result is cut off, it asks the model to complete the partial text. Then it moves on to a backup model.
- **Squadron events.** If the story names none of the pilots who were promoted, decorated, transferred or became casualties, it appends a short "Squadron update:" sentence listing them.
- **Last resort.** If every model fails, it publishes a plain factual paragraph built in code. A dull true entry beats an exciting false one.

Recommended on top of that, because they are cheap to check:

- **Every mandatory fact by name.** Check each KIA, MIA, award and promotion individually, not just one of them. The tracker's check passes as soon as any one name appears.
- **Banned phrasing.** For each `flight_results` entry whose `kill_cause` is not `shot_down`, check that "shot down" does not appear in the same sentence as that pilot's name. Retry if it does.

## 5. Continuity across journal entries (optional)

To make entries read as one story, the tracker passes a small memory object along with each new mission:

- the last 10 one-line mission summaries (`recent_events`);
- titles already used (`used_titles`), so the model doesn't repeat them;
- fallen comrades with dates, which the model may reference once in a later chapter;
- one memorable sentence per earlier chapter, extracted by a second short model call.

The tracker forbids re-introducing the squadron and the strategic situation once `recent_events` is non-empty. Without that rule, every entry opens with the same scene-setting paragraph.
