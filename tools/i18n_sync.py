"""
i18n sync tool: adds keys present in en.json but missing from other locale files.
Run from project root: python tools/i18n_sync.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
LOCALES = ROOT / "locales"


def deep_set(obj: dict, keys: list, value):
    """Set obj[keys[0]][keys[1]]...[keys[-1]] = value, creating dicts as needed."""
    for k in keys[:-1]:
        obj = obj.setdefault(k, {})
    if keys[-1] not in obj:
        obj[keys[-1]] = value
        return True  # was missing
    return False  # already existed


def load(lang: str) -> dict:
    with open(LOCALES / f"{lang}.json", encoding="utf-8") as f:
        return json.load(f)


def save(lang: str, data: dict):
    with open(LOCALES / f"{lang}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# Translations: keys missing from DE only (10 keys)
# ---------------------------------------------------------------------------
DE_ONLY = {
    # control_gui.button
    ("control_gui", "button", "career_service_record"):
        "Karriere-Gefechtsbericht",
    # control_gui.message
    ("control_gui", "message", "career_service_record_not_found"):
        "Karriere-Gefechtsbericht-Programm nicht gefunden:",
    ("control_gui", "message", "error_open_career_service_record"):
        "Karriere-Gefechtsbericht konnte nicht ge\u00f6ffnet werden.",
    # service_record
    ("service_record", "career_app_title"):
        "IL-2 Karriere-Gefechtsbericht",
    # ui.career
    ("ui", "career", "no_careers_found"):
        "Keine Karrieredaten gefunden.",
    ("ui", "career", "section_title"):
        "IL-2 Karriere",
    ("ui", "career", "theatre_chain_label"):
        "Theaterkette",
    # ui.landing
    ("ui", "landing", "campaign_section"):
        "Kampagnen-Tracker",
    ("ui", "landing", "career_section"):
        "IL-2 Karriere",
    # web.nav
    ("web", "nav", "back_to_careers"):
        "\u2190 Zur\u00fcck zu Karrieren",
}

# ---------------------------------------------------------------------------
# Translations: keys missing from FR / ES / RU / PL / ZH
# (includes everything in DE_ONLY plus extra web.* and progression.awards.*)
# ---------------------------------------------------------------------------

# -- French --
FR = {
    **{k: DE_ONLY[k] for k in DE_ONLY},  # inherit (will be overridden below)
    ("control_gui", "button", "career_service_record"):
        "Dossier de service de carri\u00e8re",
    ("control_gui", "message", "career_service_record_not_found"):
        "Ex\u00e9cutable du dossier de service de carri\u00e8re introuvable\u00a0:",
    ("control_gui", "message", "error_open_career_service_record"):
        "Impossible d\u2019ouvrir le dossier de service de carri\u00e8re.",
    ("service_record", "career_app_title"):
        "IL-2 Dossier de service de carri\u00e8re",
    ("ui", "career", "no_careers_found"):
        "Aucune donn\u00e9e de carri\u00e8re trouv\u00e9e.",
    ("ui", "career", "section_title"):
        "Carri\u00e8re IL-2",
    ("ui", "career", "theatre_chain_label"):
        "Cha\u00eene de th\u00e9\u00e2tres",
    ("ui", "landing", "campaign_section"):
        "Suivi des campagnes",
    ("ui", "landing", "career_section"):
        "Carri\u00e8re IL-2",
    ("web", "nav", "back_to_careers"):
        "\u2190 Retour aux carri\u00e8res",
    # web.label
    ("web", "label", "appointment_commander"):
        "Nomination comme commandant",
    ("web", "label", "current_squadron"):
        "Escadron actuel",
    ("web", "label", "recovery_from_injury"):
        "Convalescence apr\u00e8s blessure",
    ("web", "label", "squadron_change_to"):
        "Transfert vers {squadron}",
    # web.section
    ("web", "section", "career_summary"):
        "R\u00e9sum\u00e9 de carri\u00e8re",
    ("web", "section", "career_timeline"):
        "Chronologie de la carri\u00e8re",
    ("web", "section", "other_incidences"):
        "Autres incidents",
    # web.stat
    ("web", "stat", "days_word"):
        "jours",
    ("web", "stat", "pcp_score"):
        "Score PCP",
    # progression.awards (German Luftwaffe awards)
    ("progression", "awards", "attack_bronze"):
        "Insigne d\u2019assaut au sol en bronze",
    ("progression", "awards", "attack_gold"):
        "Insigne d\u2019assaut au sol en or",
    ("progression", "awards", "attack_gold_clasp"):
        "Insigne d\u2019assaut au sol en or avec pendentif",
    ("progression", "awards", "attack_heavy_fighters_bronze"):
        "Insigne d\u2019assaut pour chasseurs lourds en bronze",
    ("progression", "awards", "attack_heavy_fighters_gold"):
        "Insigne d\u2019assaut pour chasseurs lourds en or",
    ("progression", "awards", "attack_heavy_fighters_gold_clasp"):
        "Insigne d\u2019assaut pour chasseurs lourds en or avec pendentif",
    ("progression", "awards", "attack_heavy_fighters_silver"):
        "Insigne d\u2019assaut pour chasseurs lourds en argent",
    ("progression", "awards", "attack_silver"):
        "Insigne d\u2019assaut au sol en argent",
    ("progression", "awards", "bomber_gold"):
        "Insigne de vol op\u00e9rationnel pour bombardiers en or",
    ("progression", "awards", "bombers_bronze"):
        "Insigne de vol op\u00e9rationnel pour bombardiers en bronze",
    ("progression", "awards", "bombers_gold_clasp"):
        "Insigne de vol op\u00e9rationnel pour bombardiers en or avec pendentif",
    ("progression", "awards", "bombers_silver"):
        "Insigne de vol op\u00e9rationnel pour bombardiers en argent",
    ("progression", "awards", "eastern_front_medal"):
        "M\u00e9daille de la campagne d\u2019hiver \u00e0 l\u2019Est",
    ("progression", "awards", "fighters_bronze"):
        "Insigne de vol op\u00e9rationnel pour chasseurs en bronze",
    ("progression", "awards", "fighters_gold"):
        "Insigne de vol op\u00e9rationnel pour chasseurs en or",
    ("progression", "awards", "fighters_gold_clasp"):
        "Insigne de vol op\u00e9rationnel pour chasseurs en or avec pendentif",
    ("progression", "awards", "fighters_silver"):
        "Insigne de vol op\u00e9rationnel pour chasseurs en argent",
    ("progression", "awards", "german_cross_gold"):
        "Croix allemande en or",
    ("progression", "awards", "honor_clasp"):
        "Agrafe d\u2019honneur de la Luftwaffe",
    ("progression", "awards", "iron_cross_1st"):
        "Croix de fer de 1\u00e8re classe",
    ("progression", "awards", "iron_cross_2nd"):
        "Croix de fer de 2\u00e8me classe",
    ("progression", "awards", "knights_cross"):
        "Croix de chevalier de la Croix de fer",
    ("progression", "awards", "knights_cross_diamonds"):
        "Croix de chevalier avec diamants",
    ("progression", "awards", "knights_cross_gold_diamonds"):
        "Croix de chevalier avec feuilles de ch\u00eane en or, glaives et diamants",
    ("progression", "awards", "knights_cross_oak_leaves"):
        "Croix de chevalier avec feuilles de ch\u00eane",
    ("progression", "awards", "knights_cross_swords"):
        "Croix de chevalier avec feuilles de ch\u00eane et glaives",
    ("progression", "awards", "kuban_shield"):
        "Bouclier du Kouban",
    ("progression", "awards", "transport_bronze"):
        "Insigne de vol op\u00e9rationnel pour transports en bronze",
    ("progression", "awards", "transport_gold"):
        "Insigne de vol op\u00e9rationnel pour transports en or",
    ("progression", "awards", "transport_gold_clasp"):
        "Insigne de vol op\u00e9rationnel pour transports en or avec pendentif",
    ("progression", "awards", "transport_silver"):
        "Insigne de vol op\u00e9rationnel pour transports en argent",
    ("progression", "awards", "wound_badge_black"):
        "Insigne des bless\u00e9s en noir",
    ("progression", "awards", "wound_badge_gold"):
        "Insigne des bless\u00e9s en or",
    ("progression", "awards", "wound_badge_silver"):
        "Insigne des bless\u00e9s en argent",
}

# -- Spanish --
ES = {
    ("control_gui", "button", "career_service_record"):
        "Historial de servicio de carrera",
    ("control_gui", "message", "career_service_record_not_found"):
        "No se encontr\u00f3 el ejecutable del historial de servicio de carrera:",
    ("control_gui", "message", "error_open_career_service_record"):
        "No se pudo abrir el historial de servicio de carrera.",
    ("service_record", "career_app_title"):
        "IL-2 Historial de servicio de carrera",
    ("ui", "career", "no_careers_found"):
        "No se encontraron datos de carrera.",
    ("ui", "career", "section_title"):
        "Carrera IL-2",
    ("ui", "career", "theatre_chain_label"):
        "Cadena de teatros",
    ("ui", "landing", "campaign_section"):
        "Rastreador de campa\u00f1as",
    ("ui", "landing", "career_section"):
        "Carrera IL-2",
    ("web", "nav", "back_to_careers"):
        "\u2190 Volver a carreras",
    ("web", "label", "appointment_commander"):
        "Nombramiento como comandante",
    ("web", "label", "current_squadron"):
        "Escuadr\u00f3n actual",
    ("web", "label", "recovery_from_injury"):
        "Recuperaci\u00f3n de herida",
    ("web", "label", "squadron_change_to"):
        "Traslado al {squadron}",
    ("web", "section", "career_summary"):
        "Resumen de carrera",
    ("web", "section", "career_timeline"):
        "Cronolog\u00eda de la carrera",
    ("web", "section", "other_incidences"):
        "Otros incidentes",
    ("web", "stat", "days_word"):
        "d\u00edas",
    ("web", "stat", "pcp_score"):
        "Puntuaci\u00f3n PCP",
    ("progression", "awards", "attack_bronze"):
        "Insignia de ataque al suelo en bronce",
    ("progression", "awards", "attack_gold"):
        "Insignia de ataque al suelo en oro",
    ("progression", "awards", "attack_gold_clasp"):
        "Insignia de ataque al suelo en oro con colgante",
    ("progression", "awards", "attack_heavy_fighters_bronze"):
        "Insignia de ataque para cazas pesados en bronce",
    ("progression", "awards", "attack_heavy_fighters_gold"):
        "Insignia de ataque para cazas pesados en oro",
    ("progression", "awards", "attack_heavy_fighters_gold_clasp"):
        "Insignia de ataque para cazas pesados en oro con colgante",
    ("progression", "awards", "attack_heavy_fighters_silver"):
        "Insignia de ataque para cazas pesados en plata",
    ("progression", "awards", "attack_silver"):
        "Insignia de ataque al suelo en plata",
    ("progression", "awards", "bomber_gold"):
        "Presilla de vuelo de frente para bombarderos en oro",
    ("progression", "awards", "bombers_bronze"):
        "Presilla de vuelo de frente para bombarderos en bronce",
    ("progression", "awards", "bombers_gold_clasp"):
        "Presilla de vuelo de frente para bombarderos en oro con colgante",
    ("progression", "awards", "bombers_silver"):
        "Presilla de vuelo de frente para bombarderos en plata",
    ("progression", "awards", "eastern_front_medal"):
        "Medalla de la campa\u00f1a de invierno en el Este",
    ("progression", "awards", "fighters_bronze"):
        "Presilla de vuelo de frente para cazas en bronce",
    ("progression", "awards", "fighters_gold"):
        "Presilla de vuelo de frente para cazas en oro",
    ("progression", "awards", "fighters_gold_clasp"):
        "Presilla de vuelo de frente para cazas en oro con colgante",
    ("progression", "awards", "fighters_silver"):
        "Presilla de vuelo de frente para cazas en plata",
    ("progression", "awards", "german_cross_gold"):
        "Cruz alemana en oro",
    ("progression", "awards", "honor_clasp"):
        "Hebilla de honor de la Luftwaffe",
    ("progression", "awards", "iron_cross_1st"):
        "Cruz de Hierro de 1.\u00aa clase",
    ("progression", "awards", "iron_cross_2nd"):
        "Cruz de Hierro de 2.\u00aa clase",
    ("progression", "awards", "knights_cross"):
        "Cruz de Caballero de la Cruz de Hierro",
    ("progression", "awards", "knights_cross_diamonds"):
        "Cruz de Caballero con diamantes",
    ("progression", "awards", "knights_cross_gold_diamonds"):
        "Cruz de Caballero con hojas de roble doradas, espadas y diamantes",
    ("progression", "awards", "knights_cross_oak_leaves"):
        "Cruz de Caballero con hojas de roble",
    ("progression", "awards", "knights_cross_swords"):
        "Cruz de Caballero con hojas de roble y espadas",
    ("progression", "awards", "kuban_shield"):
        "Escudo del Kub\u00e1n",
    ("progression", "awards", "transport_bronze"):
        "Presilla de vuelo de frente para transportes en bronce",
    ("progression", "awards", "transport_gold"):
        "Presilla de vuelo de frente para transportes en oro",
    ("progression", "awards", "transport_gold_clasp"):
        "Presilla de vuelo de frente para transportes en oro con colgante",
    ("progression", "awards", "transport_silver"):
        "Presilla de vuelo de frente para transportes en plata",
    ("progression", "awards", "wound_badge_black"):
        "Insignia de herido en negro",
    ("progression", "awards", "wound_badge_gold"):
        "Insignia de herido en oro",
    ("progression", "awards", "wound_badge_silver"):
        "Insignia de herido en plata",
}

# -- Russian --
RU = {
    ("control_gui", "button", "career_service_record"):
        "\u041f\u043e\u0441\u043b\u0443\u0436\u043d\u043e\u0439 \u0441\u043f\u0438\u0441\u043e\u043a \u043a\u0430\u0440\u044c\u0435\u0440\u044b",
    ("control_gui", "message", "career_service_record_not_found"):
        "\u0418\u0441\u043f\u043e\u043b\u043d\u044f\u0435\u043c\u044b\u0439 \u0444\u0430\u0439\u043b \u043f\u043e\u0441\u043b\u0443\u0436\u043d\u043e\u0433\u043e \u0441\u043f\u0438\u0441\u043a\u0430 \u043a\u0430\u0440\u044c\u0435\u0440\u044b \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d:",
    ("control_gui", "message", "error_open_career_service_record"):
        "\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0442\u043a\u0440\u044b\u0442\u044c \u043f\u043e\u0441\u043b\u0443\u0436\u043d\u043e\u0439 \u0441\u043f\u0438\u0441\u043e\u043a \u043a\u0430\u0440\u044c\u0435\u0440\u044b.",
    ("service_record", "career_app_title"):
        "IL-2 \u041f\u043e\u0441\u043b\u0443\u0436\u043d\u043e\u0439 \u0441\u043f\u0438\u0441\u043e\u043a \u043a\u0430\u0440\u044c\u0435\u0440\u044b",
    ("ui", "career", "no_careers_found"):
        "\u0414\u0430\u043d\u043d\u044b\u0435 \u043a\u0430\u0440\u044c\u0435\u0440\u044b \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u044b.",
    ("ui", "career", "section_title"):
        "\u041a\u0430\u0440\u044c\u0435\u0440\u0430 IL-2",
    ("ui", "career", "theatre_chain_label"):
        "\u0426\u0435\u043f\u043e\u0447\u043a\u0430 \u0442\u0435\u0430\u0442\u0440\u043e\u0432",
    ("ui", "landing", "campaign_section"):
        "\u0422\u0440\u0435\u043a\u0435\u0440 \u043a\u0430\u043c\u043f\u0430\u043d\u0438\u0439",
    ("ui", "landing", "career_section"):
        "\u041a\u0430\u0440\u044c\u0435\u0440\u0430 IL-2",
    ("web", "nav", "back_to_careers"):
        "\u2190 \u041d\u0430\u0437\u0430\u0434 \u043a \u043a\u0430\u0440\u044c\u0435\u0440\u0430\u043c",
    ("web", "label", "appointment_commander"):
        "\u041d\u0430\u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0435 \u043a\u043e\u043c\u0430\u043d\u0434\u0438\u0440\u043e\u043c",
    ("web", "label", "current_squadron"):
        "\u0422\u0435\u043a\u0443\u0449\u0430\u044f \u044d\u0441\u043a\u0430\u0434\u0440\u0438\u043b\u044c\u044f",
    ("web", "label", "recovery_from_injury"):
        "\u0412\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u043f\u043e\u0441\u043b\u0435 \u0440\u0430\u043d\u0435\u043d\u0438\u044f",
    ("web", "label", "squadron_change_to"):
        "\u041f\u0435\u0440\u0435\u0432\u043e\u0434 \u0432 {squadron}",
    ("web", "section", "career_summary"):
        "\u0418\u0442\u043e\u0433\u0438 \u043a\u0430\u0440\u044c\u0435\u0440\u044b",
    ("web", "section", "career_timeline"):
        "\u0425\u0440\u043e\u043d\u043e\u043b\u043e\u0433\u0438\u044f \u043a\u0430\u0440\u044c\u0435\u0440\u044b",
    ("web", "section", "other_incidences"):
        "\u041f\u0440\u043e\u0447\u0438\u0435 \u0441\u043e\u0431\u044b\u0442\u0438\u044f",
    ("web", "stat", "days_word"):
        "\u0434\u043d.",
    ("web", "stat", "pcp_score"):
        "\u041e\u0446\u0435\u043d\u043a\u0430 \u041f\u041a\u041f",
    # German awards in Russian
    ("progression", "awards", "attack_bronze"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u043d\u0430\u0437\u0435\u043c\u043d\u043e\u0433\u043e \u0448\u0442\u0443\u0440\u043c\u043e\u0432\u0438\u043a\u0430 (\u0431\u0440\u043e\u043d\u0437\u0430)",
    ("progression", "awards", "attack_gold"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u043d\u0430\u0437\u0435\u043c\u043d\u043e\u0433\u043e \u0448\u0442\u0443\u0440\u043c\u043e\u0432\u0438\u043a\u0430 (\u0437\u043e\u043b\u043e\u0442\u043e)",
    ("progression", "awards", "attack_gold_clasp"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u043d\u0430\u0437\u0435\u043c\u043d\u043e\u0433\u043e \u0448\u0442\u0443\u0440\u043c\u043e\u0432\u0438\u043a\u0430 (\u0437\u043e\u043b\u043e\u0442\u043e \u0441 \u043f\u043e\u0434\u0432\u0435\u0441\u043a\u043e\u0439)",
    ("progression", "awards", "attack_heavy_fighters_bronze"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u044d\u043a\u0438\u043f\u0430\u0436\u0430 \u0442\u044f\u0436\u0451\u043b\u044b\u0445 \u0438\u0441\u0442\u0440\u0435\u0431\u0438\u0442\u0435\u043b\u0435\u0439 (\u0431\u0440\u043e\u043d\u0437\u0430)",
    ("progression", "awards", "attack_heavy_fighters_gold"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u044d\u043a\u0438\u043f\u0430\u0436\u0430 \u0442\u044f\u0436\u0451\u043b\u044b\u0445 \u0438\u0441\u0442\u0440\u0435\u0431\u0438\u0442\u0435\u043b\u0435\u0439 (\u0437\u043e\u043b\u043e\u0442\u043e)",
    ("progression", "awards", "attack_heavy_fighters_gold_clasp"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u044d\u043a\u0438\u043f\u0430\u0436\u0430 \u0442\u044f\u0436\u0451\u043b\u044b\u0445 \u0438\u0441\u0442\u0440\u0435\u0431\u0438\u0442\u0435\u043b\u0435\u0439 (\u0437\u043e\u043b\u043e\u0442\u043e \u0441 \u043f\u043e\u0434\u0432\u0435\u0441\u043a\u043e\u0439)",
    ("progression", "awards", "attack_heavy_fighters_silver"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u044d\u043a\u0438\u043f\u0430\u0436\u0430 \u0442\u044f\u0436\u0451\u043b\u044b\u0445 \u0438\u0441\u0442\u0440\u0435\u0431\u0438\u0442\u0435\u043b\u0435\u0439 (\u0441\u0435\u0440\u0435\u0431\u0440\u043e)",
    ("progression", "awards", "attack_silver"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u043d\u0430\u0437\u0435\u043c\u043d\u043e\u0433\u043e \u0448\u0442\u0443\u0440\u043c\u043e\u0432\u0438\u043a\u0430 (\u0441\u0435\u0440\u0435\u0431\u0440\u043e)",
    ("progression", "awards", "bomber_gold"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u0444\u0440\u043e\u043d\u0442\u043e\u0432\u043e\u0433\u043e \u043b\u0451\u0442\u0447\u0438\u043a\u0430 \u0434\u043b\u044f \u0431\u043e\u043c\u0431\u0430\u0440\u0434\u0438\u0440\u043e\u0432\u0449\u0438\u043a\u043e\u0432 (\u0437\u043e\u043b\u043e\u0442\u043e)",
    ("progression", "awards", "bombers_bronze"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u0444\u0440\u043e\u043d\u0442\u043e\u0432\u043e\u0433\u043e \u043b\u0451\u0442\u0447\u0438\u043a\u0430 \u0434\u043b\u044f \u0431\u043e\u043c\u0431\u0430\u0440\u0434\u0438\u0440\u043e\u0432\u0449\u0438\u043a\u043e\u0432 (\u0431\u0440\u043e\u043d\u0437\u0430)",
    ("progression", "awards", "bombers_gold_clasp"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u0444\u0440\u043e\u043d\u0442\u043e\u0432\u043e\u0433\u043e \u043b\u0451\u0442\u0447\u0438\u043a\u0430 \u0434\u043b\u044f \u0431\u043e\u043c\u0431\u0430\u0440\u0434\u0438\u0440\u043e\u0432\u0449\u0438\u043a\u043e\u0432 (\u0437\u043e\u043b\u043e\u0442\u043e \u0441 \u043f\u043e\u0434\u0432\u0435\u0441\u043a\u043e\u0439)",
    ("progression", "awards", "bombers_silver"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u0444\u0440\u043e\u043d\u0442\u043e\u0432\u043e\u0433\u043e \u043b\u0451\u0442\u0447\u0438\u043a\u0430 \u0434\u043b\u044f \u0431\u043e\u043c\u0431\u0430\u0440\u0434\u0438\u0440\u043e\u0432\u0449\u0438\u043a\u043e\u0432 (\u0441\u0435\u0440\u0435\u0431\u0440\u043e)",
    ("progression", "awards", "eastern_front_medal"):
        "\u041c\u0435\u0434\u0430\u043b\u044c \u00ab\u0417\u0430 \u0437\u0438\u043c\u043d\u044e\u044e \u043a\u0430\u043c\u043f\u0430\u043d\u0438\u044e \u043d\u0430 \u0412\u043e\u0441\u0442\u043e\u043a\u0435\u00bb",
    ("progression", "awards", "fighters_bronze"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u0444\u0440\u043e\u043d\u0442\u043e\u0432\u043e\u0433\u043e \u043b\u0451\u0442\u0447\u0438\u043a\u0430 \u0434\u043b\u044f \u0438\u0441\u0442\u0440\u0435\u0431\u0438\u0442\u0435\u043b\u0435\u0439 (\u0431\u0440\u043e\u043d\u0437\u0430)",
    ("progression", "awards", "fighters_gold"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u0444\u0440\u043e\u043d\u0442\u043e\u0432\u043e\u0433\u043e \u043b\u0451\u0442\u0447\u0438\u043a\u0430 \u0434\u043b\u044f \u0438\u0441\u0442\u0440\u0435\u0431\u0438\u0442\u0435\u043b\u0435\u0439 (\u0437\u043e\u043b\u043e\u0442\u043e)",
    ("progression", "awards", "fighters_gold_clasp"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u0444\u0440\u043e\u043d\u0442\u043e\u0432\u043e\u0433\u043e \u043b\u0451\u0442\u0447\u0438\u043a\u0430 \u0434\u043b\u044f \u0438\u0441\u0442\u0440\u0435\u0431\u0438\u0442\u0435\u043b\u0435\u0439 (\u0437\u043e\u043b\u043e\u0442\u043e \u0441 \u043f\u043e\u0434\u0432\u0435\u0441\u043a\u043e\u0439)",
    ("progression", "awards", "fighters_silver"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u0444\u0440\u043e\u043d\u0442\u043e\u0432\u043e\u0433\u043e \u043b\u0451\u0442\u0447\u0438\u043a\u0430 \u0434\u043b\u044f \u0438\u0441\u0442\u0440\u0435\u0431\u0438\u0442\u0435\u043b\u0435\u0439 (\u0441\u0435\u0440\u0435\u0431\u0440\u043e)",
    ("progression", "awards", "german_cross_gold"):
        "\u041d\u0435\u043c\u0435\u0446\u043a\u0438\u0439 \u043a\u0440\u0435\u0441\u0442 \u0432 \u0437\u043e\u043b\u043e\u0442\u0435",
    ("progression", "awards", "honor_clasp"):
        "\u041f\u043e\u0447\u0451\u0442\u043d\u0430\u044f \u0437\u0430\u0441\u0442\u0451\u0436\u043a\u0430 \u043b\u044e\u0444\u0442\u0432\u0430\u0444\u0444\u0435",
    ("progression", "awards", "iron_cross_1st"):
        "\u0416\u0435\u043b\u0435\u0437\u043d\u044b\u0439 \u043a\u0440\u0435\u0441\u0442 1-\u0433\u043e \u043a\u043b\u0430\u0441\u0441\u0430",
    ("progression", "awards", "iron_cross_2nd"):
        "\u0416\u0435\u043b\u0435\u0437\u043d\u044b\u0439 \u043a\u0440\u0435\u0441\u0442 2-\u0433\u043e \u043a\u043b\u0430\u0441\u0441\u0430",
    ("progression", "awards", "knights_cross"):
        "\u0420\u044b\u0446\u0430\u0440\u0441\u043a\u0438\u0439 \u043a\u0440\u0435\u0441\u0442 \u0416\u0435\u043b\u0435\u0437\u043d\u043e\u0433\u043e \u043a\u0440\u0435\u0441\u0442\u0430",
    ("progression", "awards", "knights_cross_diamonds"):
        "\u0420\u044b\u0446\u0430\u0440\u0441\u043a\u0438\u0439 \u043a\u0440\u0435\u0441\u0442 \u0441 \u0431\u0440\u0438\u043b\u043b\u0438\u0430\u043d\u0442\u0430\u043c\u0438",
    ("progression", "awards", "knights_cross_gold_diamonds"):
        "\u0420\u044b\u0446\u0430\u0440\u0441\u043a\u0438\u0439 \u043a\u0440\u0435\u0441\u0442 \u0441 \u0437\u043e\u043b\u043e\u0442\u044b\u043c\u0438 \u0434\u0443\u0431\u043e\u0432\u044b\u043c\u0438 \u043b\u0438\u0441\u0442\u044c\u044f\u043c\u0438, \u043c\u0435\u0447\u0430\u043c\u0438 \u0438 \u0431\u0440\u0438\u043b\u043b\u0438\u0430\u043d\u0442\u0430\u043c\u0438",
    ("progression", "awards", "knights_cross_oak_leaves"):
        "\u0420\u044b\u0446\u0430\u0440\u0441\u043a\u0438\u0439 \u043a\u0440\u0435\u0441\u0442 \u0441 \u0434\u0443\u0431\u043e\u0432\u044b\u043c\u0438 \u043b\u0438\u0441\u0442\u044c\u044f\u043c\u0438",
    ("progression", "awards", "knights_cross_swords"):
        "\u0420\u044b\u0446\u0430\u0440\u0441\u043a\u0438\u0439 \u043a\u0440\u0435\u0441\u0442 \u0441 \u0434\u0443\u0431\u043e\u0432\u044b\u043c\u0438 \u043b\u0438\u0441\u0442\u044c\u044f\u043c\u0438 \u0438 \u043c\u0435\u0447\u0430\u043c\u0438",
    ("progression", "awards", "kuban_shield"):
        "\u041a\u0443\u0431\u0430\u043d\u0441\u043a\u0438\u0439 \u0449\u0438\u0442",
    ("progression", "awards", "transport_bronze"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u0444\u0440\u043e\u043d\u0442\u043e\u0432\u043e\u0433\u043e \u043b\u0451\u0442\u0447\u0438\u043a\u0430 \u0434\u043b\u044f \u0442\u0440\u0430\u043d\u0441\u043f\u043e\u0440\u0442\u043d\u044b\u0445 \u0441\u0430\u043c\u043e\u043b\u0451\u0442\u043e\u0432 (\u0431\u0440\u043e\u043d\u0437\u0430)",
    ("progression", "awards", "transport_gold"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u0444\u0440\u043e\u043d\u0442\u043e\u0432\u043e\u0433\u043e \u043b\u0451\u0442\u0447\u0438\u043a\u0430 \u0434\u043b\u044f \u0442\u0440\u0430\u043d\u0441\u043f\u043e\u0440\u0442\u043d\u044b\u0445 \u0441\u0430\u043c\u043e\u043b\u0451\u0442\u043e\u0432 (\u0437\u043e\u043b\u043e\u0442\u043e)",
    ("progression", "awards", "transport_gold_clasp"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u0444\u0440\u043e\u043d\u0442\u043e\u0432\u043e\u0433\u043e \u043b\u0451\u0442\u0447\u0438\u043a\u0430 \u0434\u043b\u044f \u0442\u0440\u0430\u043d\u0441\u043f\u043e\u0440\u0442\u043d\u044b\u0445 \u0441\u0430\u043c\u043e\u043b\u0451\u0442\u043e\u0432 (\u0437\u043e\u043b\u043e\u0442\u043e \u0441 \u043f\u043e\u0434\u0432\u0435\u0441\u043a\u043e\u0439)",
    ("progression", "awards", "transport_silver"):
        "\u041d\u0430\u0433\u0440\u0443\u0434\u043d\u044b\u0439 \u0437\u043d\u0430\u043a \u0444\u0440\u043e\u043d\u0442\u043e\u0432\u043e\u0433\u043e \u043b\u0451\u0442\u0447\u0438\u043a\u0430 \u0434\u043b\u044f \u0442\u0440\u0430\u043d\u0441\u043f\u043e\u0440\u0442\u043d\u044b\u0445 \u0441\u0430\u043c\u043e\u043b\u0451\u0442\u043e\u0432 (\u0441\u0435\u0440\u0435\u0431\u0440\u043e)",
    ("progression", "awards", "wound_badge_black"):
        "\u0417\u043d\u0430\u043a \u0440\u0430\u043d\u0435\u043d\u0438\u044f (\u0447\u0451\u0440\u043d\u044b\u0439)",
    ("progression", "awards", "wound_badge_gold"):
        "\u0417\u043d\u0430\u043a \u0440\u0430\u043d\u0435\u043d\u0438\u044f (\u0437\u043e\u043b\u043e\u0442\u043e\u0439)",
    ("progression", "awards", "wound_badge_silver"):
        "\u0417\u043d\u0430\u043a \u0440\u0430\u043d\u0435\u043d\u0438\u044f (\u0441\u0435\u0440\u0435\u0431\u0440\u044f\u043d\u044b\u0439)",
}

# -- Polish --
PL = {
    ("control_gui", "button", "career_service_record"):
        "Ksi\u0105\u017cka s\u0142u\u017cby kariery",
    ("control_gui", "message", "career_service_record_not_found"):
        "Nie znaleziono pliku wykonywalnego ksi\u0105\u017cki s\u0142u\u017cby kariery:",
    ("control_gui", "message", "error_open_career_service_record"):
        "Nie uda\u0142o si\u0119 otworzy\u0107 ksi\u0105\u017cki s\u0142u\u017cby kariery.",
    ("service_record", "career_app_title"):
        "IL-2 Ksi\u0105\u017cka s\u0142u\u017cby kariery",
    ("ui", "career", "no_careers_found"):
        "Nie znaleziono danych kariery.",
    ("ui", "career", "section_title"):
        "Kariera IL-2",
    ("ui", "career", "theatre_chain_label"):
        "\u0141a\u0144cuch teatr\u00f3w",
    ("ui", "landing", "campaign_section"):
        "\u015bledzenie kampanii",
    ("ui", "landing", "career_section"):
        "Kariera IL-2",
    ("web", "nav", "back_to_careers"):
        "\u2190 Powr\u00f3t do karier",
    ("web", "label", "appointment_commander"):
        "Mianowanie dow\u00f3dc\u0105",
    ("web", "label", "current_squadron"):
        "Bie\u017c\u0105ca eskadra",
    ("web", "label", "recovery_from_injury"):
        "Rekonwalescencja po urazie",
    ("web", "label", "squadron_change_to"):
        "Przeniesienie do {squadron}",
    ("web", "section", "career_summary"):
        "Podsumowanie kariery",
    ("web", "section", "career_timeline"):
        "O\u015b czasu kariery",
    ("web", "section", "other_incidences"):
        "Inne zdarzenia",
    ("web", "stat", "days_word"):
        "dni",
    ("web", "stat", "pcp_score"):
        "Wynik PCP",
    ("progression", "awards", "attack_bronze"):
        "Odznaka szturmowa w br\u0105zie",
    ("progression", "awards", "attack_gold"):
        "Odznaka szturmowa w z\u0142ocie",
    ("progression", "awards", "attack_gold_clasp"):
        "Odznaka szturmowa w z\u0142ocie z zawieszk\u0105",
    ("progression", "awards", "attack_heavy_fighters_bronze"):
        "Odznaka szturmowa niszczyciela w br\u0105zie",
    ("progression", "awards", "attack_heavy_fighters_gold"):
        "Odznaka szturmowa niszczyciela w z\u0142ocie",
    ("progression", "awards", "attack_heavy_fighters_gold_clasp"):
        "Odznaka szturmowa niszczyciela w z\u0142ocie z zawieszk\u0105",
    ("progression", "awards", "attack_heavy_fighters_silver"):
        "Odznaka szturmowa niszczyciela w srebrze",
    ("progression", "awards", "attack_silver"):
        "Odznaka szturmowa w srebrze",
    ("progression", "awards", "bomber_gold"):
        "Odznaka lot\u00f3w frontowych dla bombowc\u00f3w w z\u0142ocie",
    ("progression", "awards", "bombers_bronze"):
        "Odznaka lot\u00f3w frontowych dla bombowc\u00f3w w br\u0105zie",
    ("progression", "awards", "bombers_gold_clasp"):
        "Odznaka lot\u00f3w frontowych dla bombowc\u00f3w w z\u0142ocie z zawieszk\u0105",
    ("progression", "awards", "bombers_silver"):
        "Odznaka lot\u00f3w frontowych dla bombowc\u00f3w w srebrze",
    ("progression", "awards", "eastern_front_medal"):
        "Medal za zimow\u0105 kampani\u0119 na Wschodzie",
    ("progression", "awards", "fighters_bronze"):
        "Odznaka lot\u00f3w frontowych dla my\u015bliwc\u00f3w w br\u0105zie",
    ("progression", "awards", "fighters_gold"):
        "Odznaka lot\u00f3w frontowych dla my\u015bliwc\u00f3w w z\u0142ocie",
    ("progression", "awards", "fighters_gold_clasp"):
        "Odznaka lot\u00f3w frontowych dla my\u015bliwc\u00f3w w z\u0142ocie z zawieszk\u0105",
    ("progression", "awards", "fighters_silver"):
        "Odznaka lot\u00f3w frontowych dla my\u015bliwc\u00f3w w srebrze",
    ("progression", "awards", "german_cross_gold"):
        "Krzy\u017c Niemiec w z\u0142ocie",
    ("progression", "awards", "honor_clasp"):
        "Klamra honorowa Luftwaffe",
    ("progression", "awards", "iron_cross_1st"):
        "Krzy\u017c \u017belazny I klasy",
    ("progression", "awards", "iron_cross_2nd"):
        "Krzy\u017c \u017belazny II klasy",
    ("progression", "awards", "knights_cross"):
        "Krzy\u017c Rycerski Krzy\u017ca \u017belaznego",
    ("progression", "awards", "knights_cross_diamonds"):
        "Krzy\u017c Rycerski z brylantami",
    ("progression", "awards", "knights_cross_gold_diamonds"):
        "Krzy\u017c Rycerski ze z\u0142otymi li\u015b\u0107mi d\u0119bu, mieczami i brylantami",
    ("progression", "awards", "knights_cross_oak_leaves"):
        "Krzy\u017c Rycerski z li\u015b\u0107mi d\u0119bu",
    ("progression", "awards", "knights_cross_swords"):
        "Krzy\u017c Rycerski z li\u015b\u0107mi d\u0119bu i mieczami",
    ("progression", "awards", "kuban_shield"):
        "Tarcza Kuba\u0144ska",
    ("progression", "awards", "transport_bronze"):
        "Odznaka lot\u00f3w frontowych dla transportowc\u00f3w w br\u0105zie",
    ("progression", "awards", "transport_gold"):
        "Odznaka lot\u00f3w frontowych dla transportowc\u00f3w w z\u0142ocie",
    ("progression", "awards", "transport_gold_clasp"):
        "Odznaka lot\u00f3w frontowych dla transportowc\u00f3w w z\u0142ocie z zawieszk\u0105",
    ("progression", "awards", "transport_silver"):
        "Odznaka lot\u00f3w frontowych dla transportowc\u00f3w w srebrze",
    ("progression", "awards", "wound_badge_black"):
        "Odznaka za rany w czerni",
    ("progression", "awards", "wound_badge_gold"):
        "Odznaka za rany w z\u0142ocie",
    ("progression", "awards", "wound_badge_silver"):
        "Odznaka za rany w srebrze",
}

# -- Chinese --
ZH = {
    ("control_gui", "button", "career_service_record"):
        "\u804c\u4e1a\u670d\u5f79\u6863\u6848",
    ("control_gui", "message", "career_service_record_not_found"):
        "\u672a\u627e\u5230\u804c\u4e1a\u670d\u5f79\u6863\u6848\u53ef\u6267\u884c\u6587\u4ef6\uff1a",
    ("control_gui", "message", "error_open_career_service_record"):
        "\u65e0\u6cd5\u6253\u5f00\u804c\u4e1a\u670d\u5f79\u6863\u6848\u3002",
    ("service_record", "career_app_title"):
        "IL-2 \u804c\u4e1a\u670d\u5f79\u6863\u6848",
    ("ui", "career", "no_careers_found"):
        "\u672a\u627e\u5230\u804c\u4e1a\u6570\u636e\u3002",
    ("ui", "career", "section_title"):
        "IL-2 \u804c\u4e1a",
    ("ui", "career", "theatre_chain_label"):
        "\u6218\u533a\u94fe",
    ("ui", "landing", "campaign_section"):
        "\u6218\u5f79\u8ffd\u8e2a\u5668",
    ("ui", "landing", "career_section"):
        "IL-2 \u804c\u4e1a",
    ("web", "nav", "back_to_careers"):
        "\u2190 \u8fd4\u56de\u804c\u4e1a\u5217\u8868",
    ("web", "label", "appointment_commander"):
        "\u664b\u5347\u4e3a\u6307\u6325\u5b98",
    ("web", "label", "current_squadron"):
        "\u5f53\u524d\u4e2d\u961f",
    ("web", "label", "recovery_from_injury"):
        "\u4f24\u540e\u5eb7\u590d",
    ("web", "label", "squadron_change_to"):
        "\u8c03\u5f80 {squadron}",
    ("web", "section", "career_summary"):
        "\u804c\u4e1a\u6982\u8981",
    ("web", "section", "career_timeline"):
        "\u804c\u4e1a\u65f6\u95f4\u7ebf",
    ("web", "section", "other_incidences"):
        "\u5176\u4ed6\u4e8b\u4ef6",
    ("web", "stat", "days_word"):
        "\u5929",
    ("web", "stat", "pcp_score"):
        "PCP \u5206\u6570",
    ("progression", "awards", "attack_bronze"):
        "\u5bf9\u5730\u653b\u51fb\u52cb\u7ae0\uff08\u94dc\u7ea7\uff09",
    ("progression", "awards", "attack_gold"):
        "\u5bf9\u5730\u653b\u51fb\u52cb\u7ae0\uff08\u91d1\u7ea7\uff09",
    ("progression", "awards", "attack_gold_clasp"):
        "\u5bf9\u5730\u653b\u51fb\u52cb\u7ae0\uff08\u91d1\u7ea7\u5e26\u6302\u4ef6\uff09",
    ("progression", "awards", "attack_heavy_fighters_bronze"):
        "\u9a71\u9010\u673a\u653b\u51fb\u52cb\u7ae0\uff08\u94dc\u7ea7\uff09",
    ("progression", "awards", "attack_heavy_fighters_gold"):
        "\u9a71\u9010\u673a\u653b\u51fb\u52cb\u7ae0\uff08\u91d1\u7ea7\uff09",
    ("progression", "awards", "attack_heavy_fighters_gold_clasp"):
        "\u9a71\u9010\u673a\u653b\u51fb\u52cb\u7ae0\uff08\u91d1\u7ea7\u5e26\u6302\u4ef6\uff09",
    ("progression", "awards", "attack_heavy_fighters_silver"):
        "\u9a71\u9010\u673a\u653b\u51fb\u52cb\u7ae0\uff08\u9280\u7ea7\uff09",
    ("progression", "awards", "attack_silver"):
        "\u5bf9\u5730\u653b\u51fb\u52cb\u7ae0\uff08\u9280\u7ea7\uff09",
    ("progression", "awards", "bomber_gold"):
        "\u8f70\u70b8\u673a\u524d\u7ebf\u98de\u884c\u626d\uff08\u91d1\u7ea7\uff09",
    ("progression", "awards", "bombers_bronze"):
        "\u8f70\u70b8\u673a\u524d\u7ebf\u98de\u884c\u626d\uff08\u94dc\u7ea7\uff09",
    ("progression", "awards", "bombers_gold_clasp"):
        "\u8f70\u70b8\u673a\u524d\u7ebf\u98de\u884c\u626d\uff08\u91d1\u7ea7\u5e26\u6302\u4ef6\uff09",
    ("progression", "awards", "bombers_silver"):
        "\u8f70\u70b8\u673a\u524d\u7ebf\u98de\u884c\u626d\uff08\u9280\u7ea7\uff09",
    ("progression", "awards", "eastern_front_medal"):
        "\u4e1c\u7ebf\u51ac\u5b63\u6218\u5f79\u52cb\u7ae0",
    ("progression", "awards", "fighters_bronze"):
        "\u6218\u6597\u673a\u524d\u7ebf\u98de\u884c\u626d\uff08\u94dc\u7ea7\uff09",
    ("progression", "awards", "fighters_gold"):
        "\u6218\u6597\u673a\u524d\u7ebf\u98de\u884c\u626d\uff08\u91d1\u7ea7\uff09",
    ("progression", "awards", "fighters_gold_clasp"):
        "\u6218\u6597\u673a\u524d\u7ebf\u98de\u884c\u626d\uff08\u91d1\u7ea7\u5e26\u6302\u4ef6\uff09",
    ("progression", "awards", "fighters_silver"):
        "\u6218\u6597\u673a\u524d\u7ebf\u98de\u884c\u626d\uff08\u9280\u7ea7\uff09",
    ("progression", "awards", "german_cross_gold"):
        "\u5fb7\u610f\u5341\u5b57\u52cb\u7ae0\uff08\u91d1\u7ea7\uff09",
    ("progression", "awards", "honor_clasp"):
        "\u7a7a\u519b\u8363\u8a89\u82b1\u540d\u518c\u626d",
    ("progression", "awards", "iron_cross_1st"):
        "\u94c1\u5341\u5b57\u52cb\u7ae0\uff08\u4e00\u7ea7\uff09",
    ("progression", "awards", "iron_cross_2nd"):
        "\u94c1\u5341\u5b57\u52cb\u7ae0\uff08\u4e8c\u7ea7\uff09",
    ("progression", "awards", "knights_cross"):
        "\u9a91\u58eb\u5341\u5b57\u94c1\u5341\u5b57\u52cb\u7ae0",
    ("progression", "awards", "knights_cross_diamonds"):
        "\u9a91\u58eb\u5341\u5b57\u52cb\u7ae0\uff08\u9503\u77f3\u7ea7\uff09",
    ("progression", "awards", "knights_cross_gold_diamonds"):
        "\u9a91\u58eb\u5341\u5b57\u52cb\u7ae0\uff08\u91d1\u6a61\u6811\u53f6\u3001\u5251\u548c\u9503\u77f3\u7ea7\uff09",
    ("progression", "awards", "knights_cross_oak_leaves"):
        "\u9a91\u58eb\u5341\u5b57\u52cb\u7ae0\uff08\u6a61\u6811\u53f6\u7ea7\uff09",
    ("progression", "awards", "knights_cross_swords"):
        "\u9a91\u58eb\u5341\u5b57\u52cb\u7ae0\uff08\u6a61\u6811\u53f6\u548c\u5251\u7ea7\uff09",
    ("progression", "awards", "kuban_shield"):
        "\u5e93\u73ed\u76fe\u724c",
    ("progression", "awards", "transport_bronze"):
        "\u8fd0\u8f93\u673a\u524d\u7ebf\u98de\u884c\u626d\uff08\u94dc\u7ea7\uff09",
    ("progression", "awards", "transport_gold"):
        "\u8fd0\u8f93\u673a\u524d\u7ebf\u98de\u884c\u626d\uff08\u91d1\u7ea7\uff09",
    ("progression", "awards", "transport_gold_clasp"):
        "\u8fd0\u8f93\u673a\u524d\u7ebf\u98de\u884c\u626d\uff08\u91d1\u7ea7\u5e26\u6302\u4ef6\uff09",
    ("progression", "awards", "transport_silver"):
        "\u8fd0\u8f93\u673a\u524d\u7ebf\u98de\u884c\u626d\uff08\u9280\u7ea7\uff09",
    ("progression", "awards", "wound_badge_black"):
        "\u6218\u4f24\u52cb\u7ae0\uff08\u9ed1\u8272\uff09",
    ("progression", "awards", "wound_badge_gold"):
        "\u6218\u4f24\u52cb\u7ae0\uff08\u91d1\u8272\uff09",
    ("progression", "awards", "wound_badge_silver"):
        "\u6218\u4f24\u52cb\u7ae0\uff08\u9280\u8272\uff09",
}

# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------
LANG_DATA = {
    "de": DE_ONLY,
    "fr": FR,
    "es": ES,
    "ru": RU,
    "pl": PL,
    "zh": ZH,
}

report = {}
for lang, translations in LANG_DATA.items():
    data = load(lang)
    added = []
    for key_tuple, value in translations.items():
        was_added = deep_set(data, list(key_tuple), value)
        if was_added:
            added.append(".".join(key_tuple))
    if added:
        save(lang, data)
        report[lang] = added
    else:
        report[lang] = []

print("=== i18n sync report ===")
for lang, keys in report.items():
    print(f"\n{lang}.json: {len(keys)} keys added")
    for k in sorted(keys):
        print(f"  + {k}")
