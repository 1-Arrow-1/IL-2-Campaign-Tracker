"""
cp.db maintenance helpers.

These functions open their own writable sqlite3 connection (the main
CareerDatabase layer is read-only).  They are intended to be called once
at application startup — before any data is served — so the UI always
sees consistent values.
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def fix_pilot_kill_plane_totals(db_path: Path) -> None:
    """
    Reconcile the parent kill-plane counters against their sub-category sums.

    The game sometimes updates killLightFighter / killLightBomber / … but
    leaves the parent rollup (killLightPlane / killMediumPlane /
    killHeavyPlane) stale.  This causes the Squadron Statistics table to
    show incorrect aircraft-kill totals.

    The fix is applied only to AI pilots (AILevel > 0) in the player's
    current active squadron(s).  The player's own row is left untouched
    because the game tracks it separately.

    Sub-category → parent mapping (same as the reference script):
        killLightPlane  = sum(killLightFighter, killLightAttackPlane,
                              killLightBomber,  killLightRecon,
                              killLightTransport)
        killMediumPlane = sum(killMediumFighter, killMediumAttackPlane,
                              killMediumBomber,  killMediumRecon,
                              killMediumTransport)
        killHeavyPlane  = sum(killHeavyFighter, killHeavyAttackPlane,
                              killHeavyBomber,  killHeavyRecon,
                              killHeavyTransport)
    """
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Find the player's current squadron(s) — one per active career segment.
        # Find only the current (most-recent) active career's squadron.
        # Historical squads are never displayed, so fixing their pilots is unnecessary.
        cursor.execute(
            """
            SELECT p.squadronId
            FROM   career c
            JOIN   pilot  p ON p.id = c.playerId
            WHERE  c.isDeleted = 0
            ORDER BY c.id DESC
            LIMIT  1
            """
        )
        row = cursor.fetchone()
        if row is None:
            logger.debug("db_maintenance: no active career found; skipping kill-plane fix")
            return
        squadron_ids = [row["squadronId"]]

        total_adjusted = 0

        for squadron_id in squadron_ids:
            # Fetch only AI pilots in this squadron
            cursor.execute(
                """
                SELECT id,
                       killLightPlane,
                       killLightFighter, killLightAttackPlane, killLightBomber,
                       killLightRecon,   killLightTransport,
                       killMediumPlane,
                       killMediumFighter, killMediumAttackPlane, killMediumBomber,
                       killMediumRecon,   killMediumTransport,
                       killHeavyPlane,
                       killHeavyFighter, killHeavyAttackPlane, killHeavyBomber,
                       killHeavyRecon,   killHeavyTransport
                FROM   pilot
                WHERE  squadronId = ?
                  AND  AILevel    > 0
                """,
                (squadron_id,),
            )
            pilots = cursor.fetchall()

            for p in pilots:
                pilot_id = p["id"]

                light_sum  = (p["killLightFighter"]  + p["killLightAttackPlane"]
                              + p["killLightBomber"]  + p["killLightRecon"]
                              + p["killLightTransport"])
                medium_sum = (p["killMediumFighter"]  + p["killMediumAttackPlane"]
                              + p["killMediumBomber"]  + p["killMediumRecon"]
                              + p["killMediumTransport"])
                heavy_sum  = (p["killHeavyFighter"]  + p["killHeavyAttackPlane"]
                              + p["killHeavyBomber"]  + p["killHeavyRecon"]
                              + p["killHeavyTransport"])

                if (p["killLightPlane"]  == light_sum
                        and p["killMediumPlane"] == medium_sum
                        and p["killHeavyPlane"]  == heavy_sum):
                    continue

                cursor.execute(
                    """
                    UPDATE pilot
                    SET    killLightPlane  = ?,
                           killMediumPlane = ?,
                           killHeavyPlane  = ?
                    WHERE  id = ?
                    """,
                    (light_sum, medium_sum, heavy_sum, pilot_id),
                )
                logger.info(
                    "db_maintenance: pilot %d (sq %d) kill-plane corrected — "
                    "Light %d→%d  Medium %d→%d  Heavy %d→%d",
                    pilot_id, squadron_id,
                    p["killLightPlane"],  light_sum,
                    p["killMediumPlane"], medium_sum,
                    p["killHeavyPlane"],  heavy_sum,
                )
                total_adjusted += 1

        conn.commit()

        if total_adjusted:
            logger.info(
                "db_maintenance: kill-plane totals corrected for %d AI pilot(s) in squadron %d",
                total_adjusted, squadron_ids[0],
            )
        else:
            logger.debug(
                "db_maintenance: kill-plane totals already consistent "
                "for all AI pilots in squadron %d",
                squadron_ids[0],
            )

    except Exception as exc:
        logger.warning("db_maintenance: fix_pilot_kill_plane_totals failed: %s", exc, exc_info=True)
    finally:
        try:
            conn.close()
        except Exception:
            pass
