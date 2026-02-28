"""
RankResolver: maps (country_int, rank_id) to a locale-aware rank name.

Two operating modes:
    standard  – game installation without rank mods; uses embedded TSV tables.
    mod       – <game_dir>/data/swf/il2/charactersranks/ folder is present;
                reads info.locale=*.txt files from per-rank sub-folders.

TSV columns:  country, rankId, eng, ger, fra, spa, pol, rus, chs
Mod folder:   {country_int}{rank_id:03d}  (e.g. "201002" for Germany Leutnant)
Mod name key: &name="<rank name>" inside info.locale=<lang>.txt

Usage:
    resolver = RankResolver(game_dir=Path('/path/to/il2'), ui_locale='de')
    rank = resolver.resolve(201, 2)   # Germany, Leutnant
    if rank:
        print(rank.english)   # "Leutnant"  (sidecar id key)
        print(rank.display)   # "Leutnant"  (localized; same here, ger=eng)
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Maps UI locale codes → game locale column/file suffixes
_UI_TO_GAME_LOCALE: Dict[str, str] = {
    'en': 'eng',
    'de': 'ger',
    'fr': 'fra',
    'es': 'spa',
    'pl': 'pol',
    'ru': 'rus',
    'zh': 'chs',
}

# Extracts rank name from &name="..." in mod info.locale=*.txt files
_NAME_RE = re.compile(r'&name="([^"]+)"')

# ---------------------------------------------------------------------------
# Embedded rank name tables (sourced from rank_names_standard.tsv /
# rank_names_mod.tsv).  Embedded for PyInstaller compatibility — no external
# file I/O at runtime.
# ---------------------------------------------------------------------------

_STANDARD_TSV: str = (
    "country\trankId\teng\tger\tfra\tspa\tpol\trus\tchs\n"
    "101\t0\tJunior Lieutenant\tMladschi Leitenant\tJunior Lieutenant\tMladshiy leytenant\tJunior Lieutenant\t\u043c\u043b\u0430\u0434\u0448\u0438\u0439 \u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u4e0a\u58eb\n"
    "101\t1\tLieutenant\tLeitenant\tLieutenant\tLeytenant\tLieutenant\t\u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u5c11\u5c09\n"
    "101\t2\tSenior Lieutenant\tStarschi Leitenant\tSenior Lieutenant\tStarshiy leytenant\tSenior Lieutenant\t\u0441\u0442\u0430\u0440\u0448\u0438\u0439 \u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u4e2d\u5c09\n"
    "101\t3\tCaptain\tKapitan\tCaptain\tKapitan\tCaptain\t\u043a\u0430\u043f\u0438\u0442\u0430\u043d\t\u4e0a\u5c09\n"
    "101\t4\tMajor\tMajor\tMajor\tMayor\tMajor\t\u043c\u0430\u0439\u043e\u0440\t\u5c11\u6821\n"
    "102\t0\tFlight Sergeant\tFlight Sergeant\tFlight Sergeant\tFlight Sergeant\tFlight Sergeant\t\u0441\u0442\u0430\u0440\u0448\u0438\u0439 \u0441\u0435\u0440\u0436\u0430\u043d\u0442\t\u4e0a\u58eb\n"
    "102\t1\tPilot Officer\tPilot Officer\tPilot Officer\tPilot Officer\tPilot Officer\t\u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u5c11\u5c09\n"
    "102\t2\tFlying Officer\tFlying Officer\tFlying Officer\tFlying Officer\tFlying Officer\t\u0441\u0442\u0430\u0440\u0448\u0438\u0439 \u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u4e2d\u5c09\n"
    "102\t3\tFlight Lieutenant\tFlight Lieutenant\tFlight Lieutenant\tFlight Lieutenant\tFlight Lieutenant\t\u043a\u0430\u043f\u0438\u0442\u0430\u043d\t\u4e0a\u5c09\n"
    "102\t4\tSquadron Leader\tSquadron Leader\tSquadron Leader\tSquadron Leader\tSquadron Leader\t\u043c\u0430\u0439\u043e\u0440\t\u5c11\u6821\n"
    "103\t0\tFlight Officer\tFlight Officer\tFlight Officer\tFlight Officer\tFlight Officer\t\u0444\u043b\u0430\u0439\u0442 \u043e\u0444\u0438\u0446\u0435\u0440\t\u51c6\u5c09\n"
    "103\t1\t2nd Lieutenant\t2nd Lieutenant\t2nd Lieutenant\t2nd Lieutenant\t2nd Lieutenant\t\u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u5c11\u5c09\n"
    "103\t2\t1st Lieutenant\t1st Lieutenant\t1st Lieutenant\t1st Lieutenant\t1st Lieutenant\t\u0441\u0442\u0430\u0440\u0448\u0438\u0439 \u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u4e2d\u5c09\n"
    "103\t3\tCaptain\tCaptain\tCaptain\tCaptain\tCaptain\t\u043a\u0430\u043f\u0438\u0442\u0430\u043d\t\u4e0a\u5c09\n"
    "103\t4\tMajor\tMajor\tMajor\tMajor\tMajor\t\u043c\u0430\u0439\u043e\u0440\t\u5c11\u6821\n"
    "201\t0\tFeldwebel\tFeldwebel\tFeldwebel\tFeldwebel\tFeldwebel\t\u0424\u0435\u043b\u044c\u0434\u0444\u0435\u0431\u0435\u043b\u044c\t\u6280\u672f\u519b\u58eb\n"
    "201\t1\tOberfeldwebel\tOberfeldwebel\tOberfeldwebel\tOberfeldwebel\tOberfeldwebel\t\u043e\u0431\u0435\u0440\u0444\u0435\u043b\u044c\u0434\u0444\u0435\u0431\u0435\u043b\u044c\t\u519b\u58eb\u957f\n"
    "201\t2\tLeutnant\tLeutnant\tLeutnant\tLeutnant\tLeutnant\t\u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u5c11\u5c09\n"
    "201\t3\tOberleutnant\tOberleutnant\tOberleutnant\tOberleutnant\tOberleutnant\t\u043e\u0431\u0435\u0440\u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u4e2d\u5c09\n"
    "201\t4\tHauptmann\tHauptmann\tHauptmann\tHauptmann\tHauptmann\t\u0433\u0430\u0443\u043f\u0442\u043c\u0430\u043d\t\u4e0a\u5c09\n"
)

_MOD_TSV: str = (
    "country\trankId\teng\tger\tfra\tspa\tpol\trus\tchs\n"
    "101\t0\tEfreitor\tEfreitor\tEfreitor\tEfreitor\tEfreitor\t\u0415\u0444\u0440\u0435\u0439\u0442\u043e\u0440\t\u4e0b\u7b49\u5175\n"
    "101\t1\tJunior Sergeant\tMladshiy serzhant\tJunior Sergeant\tMladshiy serzhant\tJunior Sergeant\t\u041c\u043b\u0430\u0434\u0448\u0438\u0439 \u0441\u0435\u0440\u0436\u0430\u043d\u0442\t\u5c11\u58eb\n"
    "101\t2\tSergeant\tSerzhant\tSergeant\tSerzhant\tSerzhant\t\u0421\u0435\u0440\u0436\u0430\u043d\u0442\t\u4e2d\u58eb\n"
    "101\t3\tSenior Sergeant\tStarshiy serzhant\tSenior Sergeant\tStarshiy serzhant\tSenior Sergeant\t\u0421\u0442\u0430\u0440\u0448\u0438\u0439 \u0441\u0435\u0440\u0436\u0430\u043d\u0442\t\u4e0a\u58eb\n"
    "101\t4\tJunior Lieutenant\tMladschi Leitenant\tJunior Lieutenant\tMladshiy leytenant\tJunior Lieutenant\t\u043c\u043b\u0430\u0434\u0448\u0438\u0439 \u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u4e0a\u58eb\n"
    "101\t5\tLieutenant\tLeitenant\tLieutenant\tLeytenant\tLieutenant\t\u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u5c11\u5c09\n"
    "101\t6\tSenior Lieutenant\tStarschi Leitenant\tSenior Lieutenant\tStarshiy leytenant\tSenior Lieutenant\t\u0441\u0442\u0430\u0440\u0448\u0438\u0439 \u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u4e2d\u5c09\n"
    "101\t7\tCaptain\tKapitan\tCaptain\tKapitan\tCaptain\t\u043a\u0430\u043f\u0438\u0442\u0430\u043d\t\u4e0a\u5c09\n"
    "101\t8\tMajor\tMajor\tMajor\tMayor\tMajor\t\u043c\u0430\u0439\u043e\u0440\t\u5c11\u6821\n"
    "101\t9\tSub-Colonel\tPodpolkovnik\tPodpolkovnik\tPodpolkovnik\tPodpolkovnik\t\u041f\u043e\u0434\u043f\u043e\u043b\u043a\u043e\u0432\u043d\u0438\u043a\t\u4e2d\u6821\n"
    "101\t10\tColonel\tPolkovnik\tPolkovnik\tPolkovnik\tPolkovnik\t\u041f\u043e\u043b\u043a\u043e\u0432\u043d\u0438\u043a\t\u4e0a\u6821\n"
    "101\t11\tMajor General\tGeneralmajor\tMajor General\tGeneral-mayor\tGeneral-mayor\t\u0413\u0435\u043d\u0435\u0440\u0430\u043b-\u043c\u0430\u0439\u043e\u0440\t\u5c11\u5c07\n"
    "101\t12\tLieutenant General\tGeneralleutnant\tGeneral Leytenant\tGeneral-Leytenant\tGeneral-leytenant\t\u0413\u0435\u043d\u0435\u0440\u0430\u043b-\u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u4e2d\u5c07\n"
    "101\t13\tColonel General\tGeneraloberst\tGeneral-polkovnik\tGeneral-polkovnik\tGeneral-polkovnik\t\u0413\u0435\u043d\u0435\u0440\u0430\u043b-\u043f\u043e\u043b\u043a\u043e\u0432\u043d\u0438\u043a\t\u5927\u5c06\n"
    "102\t0\tCorporal\tCorporal\tCorporal\tCorporal\tCorporal\t\u041a\u0430\u043f\u0440\u0430\u043b\t\u4e0b\u58eb\n"
    "102\t1\tSergeant\tSergeant\tSergeant\tSergeant\tSergeant\t\u0441\u0435\u0440\u0436\u0430\u043d\u0442\t\u4e2d\u58eb\n"
    "102\t2\tFlight Sergeant\tFlight Sergeant\tFlight Sergeant\tFlight Sergeant\tFlight Sergeant\t\u0441\u0442\u0430\u0440\u0448\u0438\u0439 \u0441\u0435\u0440\u0436\u0430\u043d\u0442\t\u4e0a\u58eb\n"
    "102\t3\tWarrant Officer\tWarrant Officer\tWarrant Officer\tWarrant Officer\tWarrant Officer\t\u0423\u043e\u0440\u0435\u043d\u0442-\u043e\u0444\u0438\u0446\u0435\u0440\t\u51c6\u5c09\n"
    "102\t4\tPilot Officer\tPilot Officer\tPilot Officer\tPilot Officer\tPilot Officer\t\u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u5c11\u5c09\n"
    "102\t5\tFlying Officer\tFlying Officer\tFlying Officer\tFlying Officer\tFlying Officer\t\u0441\u0442\u0430\u0440\u0448\u0438\u0439 \u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u4e2d\u5c09\n"
    "102\t6\tFlight Lieutenant\tFlight Lieutenant\tFlight Lieutenant\tFlight Lieutenant\tFlight Lieutenant\t\u043a\u0430\u043f\u0438\u0442\u0430\u043d\t\u4e0a\u5c09\n"
    "102\t7\tSquadron Leader\tSquadron Leader\tSquadron Leader\tSquadron Leader\tSquadron Leader\t\u043c\u0430\u0439\u043e\u0440\t\u5c11\u6821\n"
    "102\t8\tWing Commander\tWing Commander\tWing Commander\tWing Commander\tWing Commander\t\u0412\u0438\u043d\u0433 \u041a\u043e\u043c\u043c\u0430\u043d\u0434\u0435\u0440\t\u4e2d\u6821\n"
    "102\t9\tGroup Captain\tGroup Captain\tGroup Captain\tGroup Captain\tGroup Captain\t\u0413\u0440\u0443\u043f \u041a\u0430\u043f\u0442\u0435\u043d\t\u4e0a\u6821\n"
    "102\t10\tAir Commodore\tAir Commodore\tAir Commodore\tAir Commodore\tAir Commodore\t\u0430\u0432\u0438\u0430\u043a\u043e\u043c\u043c\u043e\u0434\u043e\u0440\t\u7a7a\u519b\u51c6\u5c06\n"
    "102\t11\tAir Vice Marshal\tAir Vice Marshal\tAir Vice Marshal\tAir Vice Marshal\tAir Vice Marshal\t\u0432\u0438\u0446\u0435-\u043c\u0430\u0440\u0448\u0430\u043b \u0430\u0432\u0438\u0430\u0446\u0438\u0438\t\u7a7a\u519b\u4e2d\u5c06\n"
    "102\t12\tAir Marshal\tAir Marshal\tAir Marshal\tAir Marshal\tAir Marshal\t\u043c\u0430\u0440\u0448\u0430\u043b \u0430\u0432\u0438\u0430\u0446\u0438\u0438\t\u7a7a\u519b\u4e0a\u5c06\n"
    "102\t13\tAir Chief Marshal\tAir Chief Marshal\tAir Chief Marshal\tAir Chief Marshal\tAir Chief Marshal\t\u0413\u043b\u0430\u0432\u043d\u044b\u0439 \u043c\u0430\u0440\u0448\u0430\u043b \u0430\u0432\u0438\u0430\u0446\u0438\u0438\t\u7a7a\u519b\u4e0a\u5c06\n"
    "103\t0\tStaff Sergeant\tStaff Sergeant\tStaff Sergeant\tStaff Sergeant\tStaff Sergeant\t\u0421\u0442\u0430\u0444\u0444 \u0421\u0435\u0440\u0436\u0435\u043d\u0442\t\u4e0a\u58eb\n"
    "103\t1\tTechnical Sergeant\tTechnical Sergeant\tTechnical Sergeant\tTechnical Sergeant\tTechnical Sergeant\t\u0422\u0435\u043a\u043d\u0438\u043a\u0430\u043b \u0421\u0435\u0440\u0436\u0435\u043d\u0442\t\u6280\u672f\u519b\u58eb\n"
    "103\t2\tFirst Sergeant\tFirst Sergeant\tFirst Sergeant\tFirst Sergeant\tFirst Sergeant\t\u0424\u0451\u0440\u0441\u0442 \u0421\u0435\u0440\u0436\u0435\u043d\u0442\t\u7b2c\u4e00\u519b\u58eb\n"
    "103\t3\tFlight Officer\tFlight Officer\tFlight Officer\tFlight Officer\tFlight Officer\t\u0444\u043b\u0430\u0439\u0442 \u043e\u0444\u0438\u0446\u0435\u0440\t\u51c6\u5c09\n"
    "103\t4\tChief Warrant Officer\tChief Warrant Officer\tChief Warrant Officer\tChief Warrant Officer\tChief Warrant Officer\t\u0427\u0438\u0444 \u0423\u043e\u0440\u0435\u043d\u0442 \u041e\u0444\u0438\u0446\u0435\u0440\t\u9ad8\u7ea7\u51c6\u5c09\n"
    "103\t5\t2nd Lieutenant\t2nd Lieutenant\t2nd Lieutenant\t2nd Lieutenant\t2nd Lieutenant\t\u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u5c11\u5c09\n"
    "103\t6\t1st Lieutenant\t1st Lieutenant\t1st Lieutenant\t1st Lieutenant\t1st Lieutenant\t\u0441\u0442\u0430\u0440\u0448\u0438\u0439 \u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u4e2d\u5c09\n"
    "103\t7\tCaptain\tCaptain\tCaptain\tCaptain\tCaptain\t\u043a\u0430\u043f\u0438\u0442\u0430\u043d\t\u4e0a\u5c09\n"
    "103\t8\tMajor\tMajor\tMajor\tMajor\tMajor\t\u043c\u0430\u0439\u043e\u0440\t\u5c11\u6821\n"
    "103\t9\tLt. Colonel\tLt. Colonel\tLt. Colonel\tLt. Colonel\tLt. Colonel\t\u041b\u0442. \u041a\u043e\u043b\u043e\u043d\u0435\u043b\t\u4e2d\u6821\n"
    "103\t10\tColonel\tColonel\tColonel\tColonel\tColonel\t\u041a\u043e\u043b\u043e\u043d\u0435\u043b\t\u4e0a\u6821\n"
    "103\t11\tBrigadier General\tBrigadier General\tBrigadier General\tBrigadier General\tBrigadier General\t\u0431\u0440\u0438\u0433\u0430\u0434\u043d\u044b\u0439 \u0433\u0435\u043d\u0435\u0440\u0430\u043b\t\u51c6\u5c06\n"
    "103\t12\tMajor General\tMajor General\tMajor General\tMajor General\tMajor General\t\u0433\u0435\u043d\u0435\u0440\u0430\u043b-\u043c\u0430\u0439\u043e\u0440\t\u5c11\u5c06\n"
    "103\t13\tLt. General\tLt. General\tLt. General\tLt. General\tLt. General\t\u0433\u0435\u043d\u0435\u0440\u0430\u043b-\u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u4e2d\u5c06\n"
    "201\t0\tGefreiter\tGefreiter\tGefreiter\tGefreiter\tGefreiter\t\u0424\u0445\u0439. \u0413\u0435\u0444\u0440\u0430\u0439\u0442\u0435\u0440\t\u4e0b\u7b49\u5175\n"
    "201\t1\tUnteroffizier\tUnteroffizier\tUnteroffizier\tUnteroffizier\tUnteroffizier\t\u0423\u043d\u0442\u0435\u0440\u043e\u0444\u0438\u0446\u0435\u0440\t\u4e0b\u58eb\n"
    "201\t2\tFeldwebel\tFeldwebel\tFeldwebel\tFeldwebel\tFeldwebel\t\u0424\u0435\u043b\u044c\u0434\u0444\u0435\u0431\u0435\u043b\u044c\t\u4e2d\u58eb\n"
    "201\t3\tOberfeldwebel\tOberfeldwebel\tOberfeldwebel\tOberfeldwebel\tOberfeldwebel\t\u043e\u0431\u0435\u0440\u0444\u0435\u043b\u044c\u0434\u0444\u0435\u0431\u0435\u043b\u044c\t\u4e0a\u58eb\n"
    "201\t4\tFhj. Oberfeldwebel\tFhj. Oberfeldwebel\tFhj. Oberfeldwebel\tFhj. Oberfeldwebel\tFhj. Oberfeldwebel\t\u0424\u0445\u0439. \u043e\u0431\u0435\u0440\u0444\u0435\u043b\u044c\u0434\u0444\u0435\u0431\u0435\u043b\u044c\t\u5019\u8865\u519b\u5b98\u4e0a\u58eb\n"
    "201\t5\tLeutnant\tLeutnant\tLeutnant\tLeutnant\tLeutnant\t\u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u5c11\u5c09\n"
    "201\t6\tOberleutnant\tOberleutnant\tOberleutnant\tOberleutnant\tOberleutnant\t\u043e\u0431\u0435\u0440\u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u4e2d\u5c09\n"
    "201\t7\tHauptmann\tHauptmann\tHauptmann\tHauptmann\tHauptmann\t\u0433\u0430\u0443\u043f\u0442\u043c\u0430\u043d\t\u4e0a\u5c09\n"
    "201\t8\tMajor\tMajor\tMajor\tMajor\tMajor\t\u043c\u0430\u0439\u043e\u0440\t\u5c11\u6821\n"
    "201\t9\tOberstleutnant\tOberstleutnant\tOberstleutnant\tOberstleutnant\tOberstleutnant\t\u041e\u0431\u0435\u0440\u0441\u0442\u043b\u0435\u0439\u0442\u043d\u0430\u043d\u0442\t\u4e2d\u6821\n"
    "201\t10\tOberst\tOberst\tOberst\tOberst\tOberst\t\u041e\u0431\u0435\u0440\u0441\u0442\t\u4e0a\u6821\n"
    "201\t11\tGeneralmajor\tGeneralmajor\tOberst\tGeneralmajor\tGeneralmajor\t\u0413\u0435\u043d\u0435\u0440\u0430\u043b-\u043c\u0430\u0439\u043e\u0440\t\u5c11\u5c07\n"
    "201\t12\tGeneralleutnant\tGeneralleutnant\tGeneralleutnant\tGeneralleutnant\tGeneralleutnant\t\u0413\u0435\u043d\u0435\u0440\u0430\u043b-\u043b\u0435\u0439\u0442\u0435\u043d\u0430\u043d\u0442\t\u4e2d\u5c07\n"
    "201\t13\tGeneral der Jagdflieger\tGeneral der Jagdflieger\tGeneral der Jagdflieger\tGeneral der Jagdflieger\tGeneral der Jagdflieger\t\u0413\u0435\u043d\u0435\u0440\u0430\u043b \u0438\u0441\u0442\u0440\u0435\u0431\u0438\u0442\u0435\u043b\u044c\u043d\u043e\u0439 \u0430\u0432\u0438\u0430\u0446\u0438\u0438\t\u6230\u9b25\u6a5f\u90e8\u968a\u4e0a\u5c07\n"
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RankName:
    """Resolved rank name with both canonical English key and localized display string."""
    english: str   # canonical key for sidecar id matching (e.g. "Leutnant")
    display: str   # localized for UI (e.g. "Leutnant" in German, "лейтенант" in Russian)


# ---------------------------------------------------------------------------
# TSV parser
# ---------------------------------------------------------------------------

def _parse_tsv(content: str) -> Dict[Tuple[int, int], Dict[str, str]]:
    """Parse a rank TSV string → {(country_int, rank_id_int): {col: value}}."""
    result: Dict[Tuple[int, int], Dict[str, str]] = {}
    lines = content.strip().splitlines()
    if not lines:
        return result
    headers = lines[0].split('\t')
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split('\t')
        row = dict(zip(headers, parts))
        try:
            key = (int(row.get('country', '')), int(row.get('rankId', '')))
        except (ValueError, KeyError):
            continue
        result[key] = row
    return result


# ---------------------------------------------------------------------------
# RankResolver
# ---------------------------------------------------------------------------

class RankResolver:
    """
    Resolves (country_int, rank_id) → RankName(english, display).

    Build once at application startup; results are cached internally.
    Detects mod mode automatically from the game directory.
    """

    def __init__(self, game_dir: Optional[Path], ui_locale: str = 'en'):
        """
        Args:
            game_dir:   Path to the IL-2 game root directory (may be None).
            ui_locale:  UI locale code, e.g. 'en', 'de', 'ru'.
        """
        self._game_locale = _UI_TO_GAME_LOCALE.get(ui_locale, 'eng')

        # Detect mod: <game_dir>/data/swf/il2/charactersranks must exist
        self._mod_dir: Optional[Path] = None
        if game_dir:
            candidate = game_dir / 'data' / 'swf' / 'il2' / 'charactersranks'
            if candidate.is_dir():
                self._mod_dir = candidate
                logger.info("RankResolver: mod mode active (%s)", candidate)

        tsv = _MOD_TSV if self._mod_dir else _STANDARD_TSV
        self._tsv_table = _parse_tsv(tsv)
        self._cache: Dict[Tuple[int, int], Optional[RankName]] = {}

        logger.info(
            "RankResolver: %s mode, locale=%s (%s), %d TSV entries loaded",
            "mod" if self._mod_dir else "standard",
            ui_locale, self._game_locale,
            len(self._tsv_table),
        )

    @classmethod
    def disabled(cls) -> "RankResolver":
        """Return a no-op resolver (standard TSV, English only, no game_dir)."""
        return cls(game_dir=None, ui_locale='en')

    # ------------------------------------------------------------------

    def resolve(self, country_int: int, rank_id: int) -> Optional[RankName]:
        """
        Return RankName for (country_int, rank_id), or None if unknown.

        Results are cached after the first lookup.
        """
        key = (country_int, rank_id)
        if key not in self._cache:
            self._cache[key] = self._resolve_uncached(country_int, rank_id)
        return self._cache[key]

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _resolve_uncached(self, country_int: int, rank_id: int) -> Optional[RankName]:
        if self._mod_dir is not None:
            return self._resolve_from_mod(country_int, rank_id)
        return self._resolve_from_tsv(country_int, rank_id)

    def _resolve_from_mod(self, country_int: int, rank_id: int) -> Optional[RankName]:
        folder = self._mod_dir / f"{country_int}{rank_id:03d}"
        if not folder.is_dir():
            logger.debug("RankResolver: mod folder not found: %s", folder)
            return None
        english = self._read_mod_locale(folder, 'eng')
        if not english:
            logger.debug("RankResolver: no eng name in %s", folder)
            return None
        display = self._read_mod_locale(folder, self._game_locale) or english
        return RankName(english=english, display=display)

    def _resolve_from_tsv(self, country_int: int, rank_id: int) -> Optional[RankName]:
        row = self._tsv_table.get((country_int, rank_id))
        if row is None:
            logger.debug("RankResolver: no TSV entry for (%d, %d)", country_int, rank_id)
            return None
        english = row.get('eng', '').strip()
        if not english:
            return None
        display = (row.get(self._game_locale) or '').strip() or english
        return RankName(english=english, display=display)

    @staticmethod
    def _read_mod_locale(folder: Path, lang: str) -> Optional[str]:
        """Read &name="..." from info.locale=<lang>.txt inside the folder."""
        p = folder / f"info.locale={lang}.txt"
        if not p.exists():
            return None
        try:
            text = p.read_text(encoding='utf-8', errors='replace')
            m = _NAME_RE.search(text)
            return m.group(1) if m else None
        except Exception as exc:
            logger.debug("RankResolver: failed to read %s: %s", p, exc)
            return None
