"""
IL-2 Settings Manager - Internationalization

Manages translations with fallback to English.
Reuses locale files from the main tracker and adds settings-specific keys.
"""

import json
import re
from pathlib import Path
from typing import Dict, Optional

from settings_manager.config.paths import LOCALES_DIR


# Language display names
LANGUAGE_NAMES = {
    'en': 'English',
    'de': 'Deutsch',
    'es': 'Español',
    'fr': 'Français',
    'pl': 'Polski',
    'ru': 'Русский',
    'zh': '简体中文',
}

# Settings Manager specific translations (embedded)
# These supplement the main tracker's locale files
SETTINGS_TRANSLATIONS = {
    'en': {
        "app_title": "IL-2 Campaign Tracker - Settings Manager",
        "tab_general": "General",
        "tab_rank_scaling": "Rank Scaling",
        "tab_rank_values": "Rank Values",
        "tab_campaigns": "Campaigns",
        
        "lbl_language": "Language:",
        "lbl_enable_popups": "Enable in-game popups:",
        "lbl_rank_scaling_enabled": "Rank scaling enabled:",
        
        "lbl_bracket": "Bracket",
        "lbl_factor": "Factor",
        "btn_add_bracket": "Add Bracket",
        "btn_remove_bracket": "Remove Bracket",
        "btn_edit": "Edit",
        
        "lbl_rank_name": "Rank",
        "lbl_rank_index_header": "Rank Index",
        "lbl_rank_index_format": "Rank {index}",
        "lbl_rank_score": "Score",
        "lbl_rank_values_helper": "Editing scores applies to all countries.",
        
        "lbl_campaign_name": "Campaign",
        "lbl_country": "Country",
        "lbl_starting_rank_offset": "Starting Rank Offset",
        
        "btn_ok": "OK",
        "btn_apply": "Apply",
        "btn_cancel": "Cancel",
        "btn_restore_defaults": "Restore Defaults",
        
        "msg_unsaved_changes": "You have unsaved changes. Discard?",
        "msg_confirm_delete": "Delete bracket '{bracket}'?",
        "msg_save_success": "Settings saved successfully.",
        "msg_locale_refresh": "Language updated. Localized mission texts and PDFs will be refreshed.",
        "msg_locale_refresh_failed": "Language updated, but refreshing localized mission texts and PDFs failed: {error}",
        "msg_save_error": "Error saving settings: {error}",
        "msg_rank_scores_mismatch": "Scores differ between countries; applying will unify them to the edited values.",
        "msg_warning_title": "Warning",
        "msg_confirm_title": "Confirm",
        "msg_error_title": "Error",
        
        "err_bracket_format": "Invalid bracket format. Use 'A-B' or 'N+'",
        "err_bracket_duplicate": "Bracket already exists",
        "err_bracket_overlap": "Bracket overlaps with: {bracket}",
        "err_factor_range": "Factor must be between 0.1 and 10.0",
        "err_score_negative": "Score cannot be negative",
        "err_score_not_ascending": "Scores must be in ascending order (error at rank {index})",
        "err_offset_range": "Offset must be between {min} and {max}",
        
        "dlg_edit_bracket_title": "Edit Bracket",
        "dlg_edit_bracket_label": "Bracket (e.g., '1-10' or '71+'):",
        "dlg_edit_factor_label": "Factor:",
        "dlg_edit_score_title": "Edit Score",
        "dlg_edit_score_label": "Score for {rank}:",
        "dlg_edit_offset_title": "Edit Offset",
        "dlg_edit_offset_label": "Starting rank offset for {campaign}:",
        
        "tooltip_bracket": "Mission count range (e.g., '1-10', '11-20', '71+')",
        "tooltip_factor": "Score multiplier for rank requirements",
        "tooltip_offset": "Start at a higher rank (0 = lowest rank)",
        
        "msg_no_mission_dates": "Campaign settings disabled.\ncampaign_mission_dates.json not found.",
        "msg_campaigns_tab_disabled": "Campaign settings require campaign_mission_dates.json.\nPlease run the Campaign Tracker at least once.",
    },
    'de': {
        "app_title": "IL-2 Campaign Tracker - Einstellungen",
        "tab_general": "Allgemein",
        "tab_rank_scaling": "Rang-Skalierung",
        "tab_rank_values": "Rang-Werte",
        "tab_campaigns": "Kampagnen",
        
        "lbl_language": "Sprache:",
        "lbl_enable_popups": "In-Game Popups aktivieren:",
        "lbl_rank_scaling_enabled": "Rang-Skalierung aktiviert:",
        
        "lbl_bracket": "Bereich",
        "lbl_factor": "Faktor",
        "btn_add_bracket": "Bereich hinzufügen",
        "btn_remove_bracket": "Bereich entfernen",
        "btn_edit": "Bearbeiten",
        
        "lbl_rank_name": "Rang",
        "lbl_rank_index_header": "Rang-Index",
        "lbl_rank_index_format": "Rang {index}",
        "lbl_rank_score": "Punkte",
        "lbl_rank_values_helper": "Bearbeitete Punkte gelten für alle Länder.",
        
        "lbl_campaign_name": "Kampagne",
        "lbl_country": "Land",
        "lbl_starting_rank_offset": "Start-Rang Offset",
        
        "btn_ok": "OK",
        "btn_apply": "Übernehmen",
        "btn_cancel": "Abbrechen",
        "btn_restore_defaults": "Standards wiederherstellen",
        
        "msg_unsaved_changes": "Ungespeicherte Änderungen. Verwerfen?",
        "msg_confirm_delete": "Bereich '{bracket}' löschen?",
        "msg_save_success": "Einstellungen erfolgreich gespeichert.",
        "msg_locale_refresh": "Sprache aktualisiert. Lokalisierte Missions-Texte und PDFs werden aktualisiert.",
        "msg_locale_refresh_failed": "Sprache aktualisiert, aber das Aktualisieren lokalisierter Missionstexte und PDFs ist fehlgeschlagen: {error}",
        "msg_save_error": "Fehler beim Speichern: {error}",
        "msg_rank_scores_mismatch": "Punkte unterscheiden sich zwischen Ländern; Übernehmen vereinheitlicht sie auf die bearbeiteten Werte.",
        "msg_warning_title": "Warnung",
        "msg_confirm_title": "Bestätigen",
        "msg_error_title": "Fehler",
        
        "err_bracket_format": "Ungültiges Format. Verwende 'A-B' oder 'N+'",
        "err_bracket_duplicate": "Bereich existiert bereits",
        "err_bracket_overlap": "Bereich überschneidet sich mit: {bracket}",
        "err_factor_range": "Faktor muss zwischen 0.1 und 10.0 liegen",
        "err_score_negative": "Punkte dürfen nicht negativ sein",
        "err_score_not_ascending": "Punkte müssen aufsteigend sein (Fehler bei Rang {index})",
        "err_offset_range": "Offset muss zwischen {min} und {max} liegen",
        
        "dlg_edit_bracket_title": "Bereich bearbeiten",
        "dlg_edit_bracket_label": "Bereich (z.B. '1-10' oder '71+'):",
        "dlg_edit_factor_label": "Faktor:",
        "dlg_edit_score_title": "Punkte bearbeiten",
        "dlg_edit_score_label": "Punkte für {rank}:",
        "dlg_edit_offset_title": "Offset bearbeiten",
        "dlg_edit_offset_label": "Start-Rang Offset für {campaign}:",
        
        "tooltip_bracket": "Missionsanzahl-Bereich (z.B. '1-10', '11-20', '71+')",
        "tooltip_factor": "Punkte-Multiplikator für Rang-Anforderungen",
        "tooltip_offset": "Bei höherem Rang starten (0 = niedrigster Rang)",
        
        "msg_no_mission_dates": "Kampagnen-Einstellungen deaktiviert.\ncampaign_mission_dates.json nicht gefunden.",
        "msg_campaigns_tab_disabled": "Kampagnen-Einstellungen erfordern campaign_mission_dates.json.\nBitte führe den Campaign Tracker mindestens einmal aus.",
    },
    'es': {
        "app_title": "IL-2 Campaign Tracker - Configuración",
        "tab_general": "General",
        "tab_rank_scaling": "Escalado de Rango",
        "tab_rank_values": "Valores de Rango",
        "tab_campaigns": "Campañas",
        
        "lbl_language": "Idioma:",
        "lbl_enable_popups": "Activar popups en juego:",
        "lbl_rank_scaling_enabled": "Escalado de rango activado:",
        
        "lbl_bracket": "Rango",
        "lbl_factor": "Factor",
        "btn_add_bracket": "Añadir Rango",
        "btn_remove_bracket": "Eliminar Rango",
        "btn_edit": "Editar",
        
        "lbl_rank_name": "Rango",
        "lbl_rank_index_header": "Índice de rango",
        "lbl_rank_index_format": "Rango {index}",
        "lbl_rank_score": "Puntuación",
        "lbl_rank_values_helper": "La edición de puntuaciones se aplica a todos los países.",
        
        "lbl_campaign_name": "Campaña",
        "lbl_country": "País",
        "lbl_starting_rank_offset": "Offset de Rango Inicial",
        
        "btn_ok": "Aceptar",
        "btn_apply": "Aplicar",
        "btn_cancel": "Cancelar",
        "btn_restore_defaults": "Restaurar Predeterminados",
        
        "msg_unsaved_changes": "Tienes cambios sin guardar. ¿Descartar?",
        "msg_confirm_delete": "¿Eliminar rango '{bracket}'?",
        "msg_save_success": "Configuración guardada correctamente.",
        "msg_locale_refresh": "Idioma actualizado. Los textos de misión y los PDF localizados se actualizarán.",
        "msg_locale_refresh_failed": "Idioma actualizado, pero la actualización de los textos de misión y PDF localizados falló: {error}",
        "msg_save_error": "Error al guardar: {error}",
        "msg_rank_scores_mismatch": "Las puntuaciones difieren entre países; al aplicar se unificarán con los valores editados.",
        "msg_warning_title": "Advertencia",
        "msg_confirm_title": "Confirmar",
        "msg_error_title": "Error",
        
        "err_bracket_format": "Formato inválido. Usa 'A-B' o 'N+'",
        "err_bracket_duplicate": "El rango ya existe",
        "err_bracket_overlap": "El rango se superpone con: {bracket}",
        "err_factor_range": "El factor debe estar entre 0.1 y 10.0",
        "err_score_negative": "La puntuación no puede ser negativa",
        "err_score_not_ascending": "Las puntuaciones deben ser ascendentes (error en rango {index})",
        "err_offset_range": "El offset debe estar entre {min} y {max}",
    },
    'fr': {
        "app_title": "IL-2 Campaign Tracker - Paramètres",
        "tab_general": "Général",
        "tab_rank_scaling": "Échelle de Rang",
        "tab_rank_values": "Valeurs de Rang",
        "tab_campaigns": "Campagnes",
        
        "lbl_language": "Langue:",
        "lbl_enable_popups": "Activer les popups en jeu:",
        "lbl_rank_scaling_enabled": "Échelle de rang activée:",
        
        "lbl_bracket": "Plage",
        "lbl_factor": "Facteur",
        "btn_add_bracket": "Ajouter Plage",
        "btn_remove_bracket": "Supprimer Plage",
        "btn_edit": "Modifier",
        
        "lbl_rank_name": "Rang",
        "lbl_rank_index_header": "Indice de rang",
        "lbl_rank_index_format": "Rang {index}",
        "lbl_rank_score": "Score",
        "lbl_rank_values_helper": "La modification des scores s'applique à tous les pays.",
        
        "lbl_campaign_name": "Campagne",
        "lbl_country": "Pays",
        "lbl_starting_rank_offset": "Décalage de Rang Initial",
        
        "btn_ok": "OK",
        "btn_apply": "Appliquer",
        "btn_cancel": "Annuler",
        "btn_restore_defaults": "Restaurer les Défauts",
        
        "msg_unsaved_changes": "Vous avez des modifications non enregistrées. Annuler?",
        "msg_confirm_delete": "Supprimer la plage '{bracket}'?",
        "msg_save_success": "Paramètres enregistrés avec succès.",
        "msg_locale_refresh": "Langue mise à jour. Les textes de mission et PDF localisés seront actualisés.",
        "msg_locale_refresh_failed": "Langue mise à jour, mais l’actualisation des textes de mission et des PDF localisés a échoué : {error}",
        "msg_save_error": "Erreur lors de l'enregistrement: {error}",
        "msg_rank_scores_mismatch": "Les scores diffèrent selon les pays ; l'application les unifiera aux valeurs modifiées.",
        "msg_warning_title": "Avertissement",
        "msg_confirm_title": "Confirmer",
        "msg_error_title": "Erreur",
    },
    'pl': {
        "app_title": "IL-2 Campaign Tracker - Ustawienia",
        "tab_general": "Ogólne",
        "tab_rank_scaling": "Skalowanie Rang",
        "tab_rank_values": "Wartości Rang",
        "tab_campaigns": "Kampanie",
        
        "lbl_language": "Język:",
        "lbl_enable_popups": "Włącz powiadomienia w grze:",
        "lbl_rank_scaling_enabled": "Skalowanie rang włączone:",
        
        "lbl_bracket": "Zakres",
        "lbl_factor": "Współczynnik",
        "btn_add_bracket": "Dodaj Zakres",
        "btn_remove_bracket": "Usuń Zakres",
        "btn_edit": "Edytuj",
        
        "lbl_rank_name": "Ranga",
        "lbl_rank_index_header": "Indeks rangi",
        "lbl_rank_index_format": "Ranga {index}",
        "lbl_rank_score": "Punkty",
        "lbl_rank_values_helper": "Edycja punktów dotyczy wszystkich krajów.",
        
        "lbl_campaign_name": "Kampania",
        "lbl_country": "Kraj",
        "lbl_starting_rank_offset": "Przesunięcie Rangi Początkowej",
        
        "btn_ok": "OK",
        "btn_apply": "Zastosuj",
        "btn_cancel": "Anuluj",
        "btn_restore_defaults": "Przywróć Domyślne",
        
        "msg_unsaved_changes": "Masz niezapisane zmiany. Odrzucić?",
        "msg_confirm_delete": "Usunąć zakres '{bracket}'?",
        "msg_save_success": "Ustawienia zapisane pomyślnie.",
        "msg_locale_refresh": "Język zaktualizowany. Zlokalizowane teksty misji i pliki PDF zostaną odświeżone.",
        "msg_locale_refresh_failed": "Język zaktualizowany, ale odświeżenie zlokalizowanych tekstów misji i PDF nie powiodło się: {error}",
        "msg_save_error": "Błąd podczas zapisywania: {error}",
        "msg_rank_scores_mismatch": "Punkty różnią się między krajami; zastosowanie ujednolici je do edytowanych wartości.",
        "msg_warning_title": "Ostrzeżenie",
        "msg_confirm_title": "Potwierdź",
        "msg_error_title": "Błąd",
    },
    'ru': {
        "app_title": "IL-2 Campaign Tracker - Настройки",
        "tab_general": "Общие",
        "tab_rank_scaling": "Масштаб Званий",
        "tab_rank_values": "Значения Званий",
        "tab_campaigns": "Кампании",
        
        "lbl_language": "Язык:",
        "lbl_enable_popups": "Включить всплывающие окна:",
        "lbl_rank_scaling_enabled": "Масштабирование званий:",
        
        "lbl_bracket": "Диапазон",
        "lbl_factor": "Коэффициент",
        "btn_add_bracket": "Добавить Диапазон",
        "btn_remove_bracket": "Удалить Диапазон",
        "btn_edit": "Редактировать",
        
        "lbl_rank_name": "Звание",
        "lbl_rank_index_header": "Индекс звания",
        "lbl_rank_index_format": "Звание {index}",
        "lbl_rank_score": "Очки",
        "lbl_rank_values_helper": "Изменение очков применяется ко всем странам.",
        
        "lbl_campaign_name": "Кампания",
        "lbl_country": "Страна",
        "lbl_starting_rank_offset": "Смещение Начального Звания",
        
        "btn_ok": "OK",
        "btn_apply": "Применить",
        "btn_cancel": "Отмена",
        "btn_restore_defaults": "Восстановить По Умолчанию",
        
        "msg_unsaved_changes": "Есть несохранённые изменения. Отменить?",
        "msg_confirm_delete": "Удалить диапазон '{bracket}'?",
        "msg_save_success": "Настройки успешно сохранены.",
        "msg_locale_refresh": "Язык обновлён. Локализованные тексты миссий и PDF будут обновлены.",
        "msg_locale_refresh_failed": "Язык обновлён, но обновление локализованных текстов миссий и PDF не удалось: {error}",
        "msg_save_error": "Ошибка сохранения: {error}",
        "msg_rank_scores_mismatch": "Очки различаются между странами; применение приведёт их к изменённым значениям.",
        "msg_warning_title": "Предупреждение",
        "msg_confirm_title": "Подтверждение",
        "msg_error_title": "Ошибка",
    },
    'zh': {
        "app_title": "IL-2 战役追踪器 - 设置管理器",
        "tab_general": "通用",
        "tab_rank_scaling": "军衔缩放",
        "tab_rank_values": "军衔数值",
        "tab_campaigns": "战役",
        
        "lbl_language": "语言：",
        "lbl_enable_popups": "启用游戏内弹窗：",
        "lbl_rank_scaling_enabled": "启用军衔缩放：",
        
        "lbl_bracket": "区间",
        "lbl_factor": "系数",
        "btn_add_bracket": "添加区间",
        "btn_remove_bracket": "删除区间",
        "btn_edit": "编辑",
        
        "lbl_rank_name": "军衔",
        "lbl_rank_index_header": "等级索引",
        "lbl_rank_index_format": "等级 {index}",
        "lbl_rank_score": "分数",
        "lbl_rank_values_helper": "编辑分数会应用到所有国家。",
        
        "lbl_campaign_name": "战役",
        "lbl_country": "国家",
        "lbl_starting_rank_offset": "起始军衔偏移",
        
        "btn_ok": "确定",
        "btn_apply": "应用",
        "btn_cancel": "取消",
        "btn_restore_defaults": "恢复默认",
        
        "msg_unsaved_changes": "有未保存的更改。是否放弃？",
        "msg_confirm_delete": "删除区间 '{bracket}'？",
        "msg_save_success": "设置保存成功。",
        "msg_locale_refresh": "语言已更新。本地化任务文本和 PDF 将刷新。",
        "msg_locale_refresh_failed": "语言已更新，但刷新本地化任务文本和 PDF 失败：{error}",
        "msg_save_error": "保存错误：{error}",
        "msg_rank_scores_mismatch": "各国分数不同；应用后将统一为编辑后的值。",
        "msg_warning_title": "警告",
        "msg_confirm_title": "确认",
        "msg_error_title": "错误",
    },
}


def name_to_i18n_key(name: str) -> str:
    """Convert display name to i18n key format."""
    value = name.lower()
    value = value.replace("'", "")
    value = value.replace("&", "and")
    value = value.replace("+", "and")
    value = re.sub(r"[,\.\"]", "", value)
    value = re.sub(r"\s*\(\s*", "_", value)
    value = re.sub(r"\s*\)\s*", "", value)
    value = value.replace("…", "")
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")


def country_code_for_rank(country: Optional[str]) -> str:
    """Get country code prefix for rank i18n keys."""
    normalized = (country or "").lower().strip()
    if normalized == "germany":
        return "ger"
    if normalized in {"britain", "uk", "great britain"}:
        return "raf"
    if normalized in {"usa", "united states", "united states of america", "us"}:
        return "usaaf"
    if normalized in {"soviet union", "ussr", "russia"}:
        return "vvs"
    return ""


class Translator:
    """Manages translations with fallback to English."""
    
    SUPPORTED_LOCALES = list(LANGUAGE_NAMES.keys())
    
    def __init__(self):
        self.current_locale = 'en'
        self.translations: Dict[str, Dict[str, str]] = {}
        self.locale_data: Dict[str, dict] = {}
        self._load_all_translations()
    
    def _load_all_translations(self) -> None:
        """Load embedded translations and supplement from locale files if available."""
        # Start with embedded translations
        self.translations = {k: dict(v) for k, v in SETTINGS_TRANSLATIONS.items()}
        
        # Try to load additional strings from main tracker's locale files
        if LOCALES_DIR.exists():
            for locale in self.SUPPORTED_LOCALES:
                filepath = LOCALES_DIR / f"{locale}.json"
                if filepath.exists():
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            # Extract useful strings from main tracker
                            if locale not in self.translations:
                                self.translations[locale] = {}
                            # Add button translations
                            if 'ui' in data and 'button' in data['ui']:
                                for key, val in data['ui']['button'].items():
                                    self.translations[locale][f'btn_{key}'] = val
                    except (json.JSONDecodeError, OSError):
                        pass

    def _load_locale_data(self, locale: str) -> dict:
        """Load full locale JSON for rank translations."""
        if locale in self.locale_data:
            return self.locale_data[locale]
        data: dict = {}
        filepath = LOCALES_DIR / f"{locale}.json"
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                data = {}
        self.locale_data[locale] = data
        return data

    def _lookup_rank_translation(self, locale: str, key: str) -> Optional[str]:
        data = self._load_locale_data(locale)
        return data.get("progression", {}).get("ranks", {}).get(key)

    def translate_rank_name(self, name: str, country: Optional[str]) -> str:
        """Translate rank name using locale files with fallback to English."""
        if not name:
            return name

        base_key = name_to_i18n_key(name)
        country_code = country_code_for_rank(country)
        keys = []
        if country_code:
            keys.append(f"{country_code}_{base_key}")
        keys.append(base_key)

        for locale in (self.current_locale, 'en'):
            for key in keys:
                translated = self._lookup_rank_translation(locale, key)
                if translated:
                    return translated

        return name
    
    def set_locale(self, locale: str) -> None:
        """Set current locale."""
        if locale in self.SUPPORTED_LOCALES:
            self.current_locale = locale
    
    def t(self, key: str, **kwargs) -> str:
        """
        Translate key to current locale with optional formatting.
        Falls back to English, then to key itself.
        """
        # Try current locale
        text = self.translations.get(self.current_locale, {}).get(key)
        
        # Fallback to English
        if text is None:
            text = self.translations.get('en', {}).get(key)
        
        # Fallback to key
        if text is None:
            return key
        
        # Format with kwargs
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass
        
        return text
    
    def get_language_options(self) -> Dict[str, str]:
        """Return dict of locale_code -> display_name."""
        return LANGUAGE_NAMES.copy()
