# PHASE 3-5 Implementierungsplan

## Status-Analyse

### ✅ Bereits i18n-fähig:
1. **popups_min.py** - Nutzt bereits `from utils.i18n import t`
2. **step3_generate_events.py** - Nutzt bereits i18n
3. **utils/i18n.py** - Vollständiges i18n-System vorhanden

### ❌ Benötigen i18n-Integration:
1. **backup_restore_gui.py** - Backup/Restore GUI
2. **country_validator_gui.py** - Country Validator GUI
3. **Weitere CLI-Scripts** (falls vorhanden)

## PHASE 3: GUIs (Backup/Restore, Country Validator)

### 3.1 backup_restore_gui.py
**Hardcodierte Strings:**
- Window title: "IL-2 Campaign Tracker - Restore Backup"
- Headers: "🔄 Restore Campaign Backup"
- Messages: "Select a backup to restore...", "⚠️ Restoring a backup will..."
- Buttons: "🔄 Restore Selected Backup", "▶ Continue Without Restore", "✕ Exit"
- Status: "✅ Currently Active", "✓ Included", "✗ Not available"
- Confirmations: "Confirm Restore", "Are you sure..."

**Neue i18n Keys (ui.backup_restore):**
```json
"ui": {
  "backup_restore": {
    "title": "IL-2 Campaign Tracker - Wiederherstellung",
    "header": "Kampagnen-Sicherung wiederherstellen",
    "select_backup": "Wählen Sie eine Sicherung aus, um Ihren Kampagnenfortschritt auf einen früheren Stand wiederherzustellen",
    "warning": "⚠️ Das Wiederherstellen einer Sicherung ersetzt Ihren aktuellen Kampagnenfortschritt. Der Tracker wird nach der Wiederherstellung automatisch neu gestartet. Ihre Popup-Zustände werden ebenfalls wiederhergestellt, falls verfügbar.",
    "restore_button": "Ausgewählte Sicherung wiederherstellen",
    "continue_button": "Ohne Wiederherstellung fortfahren",
    "exit_button": "Beenden",
    "status_active": "Aktuell aktiv",
    "popups_included": "Enthalten",
    "popups_not_available": "Nicht verfügbar",
    "backups_found": "{count} Sicherung(en) gefunden in: {path}",
    "confirm_title": "Wiederherstellung bestätigen",
    "confirm_message": "Sind Sie sicher, dass Sie diese Sicherung wiederherstellen möchten?\n\n📅 Datum: {date}\n📦 Größe: {size}\n💾 Popup-Status: {popup_status}\n\nIhr aktueller Kampagnenfortschritt wird ersetzt.\nDer Tracker wird automatisch neu gestartet.",
    "popup_will_restore": "Wird wiederhergestellt",
    "popup_not_available": "Nicht verfügbar",
    "error_title": "Fehler",
    "error_no_backup": "Sicherungsinformationen nicht gefunden.",
    "size_unknown": "Unbekannt"
  }
}
```

### 3.2 country_validator_gui.py
**Hardcodierte Strings:**
- Window title
- Headers, labels
- Buttons
- Validation messages

**Neue i18n Keys (ui.country_validator):**
Analog zu backup_restore

## PHASE 4: CLI Messages

### Betroffene Dateien:
- monitor_campaigns.py
- step1_extract_mission_dates.py
- step3_generate_events.py (teilweise schon i18n)
- step4_process_mission_logs.py
- cleanup_failed_missions.py
- etc.

**Neue i18n Keys (cli):**
Bereits teilweise in de.json/en.json vorhanden:
```json
"cli": {
  "header": {...},
  "message": {...},
  "error": {...},
  "status": {...}
}
```

## PHASE 5: PDF Labels

### Betroffene Komponenten:
- PDF-Generierung (vermutlich in utils/ oder separates Script)

**Keys bereits vorhanden:**
```json
"pdf": {
  "section": {...},
  "label": {...},
  "value": {...}
}
```

## PHASE 6: Service Record Popups - Narratives

### Bereits implementiert in:
- **popups_min.py** - Nutzt bereits i18n!
- **step3_generate_events.py** - Event-Generierung mit i18n

**Keys bereits vorhanden:**
```json
"event": {
  "promotion": {
    "description": "Beförderung zum {rank}",
    "narrative": "Am {date} wurden Sie zum {rank} befördert.",
    "initial_rank": "Anfangsrang: {rank}"
  },
  "award": {
    "description": "Verleihung von {name}",
    "narrative": "Für außergewöhnliche Dienste wurden Sie mit {name} ausgezeichnet."
  }
}
```

## Implementierungs-Reihenfolge

1. ✅ **i18n Keys zu de.json/en.json hinzufügen** für backup_restore und country_validator
2. ✅ **backup_restore_gui.py** - i18n integrieren
3. ✅ **country_validator_gui.py** - i18n integrieren  
4. ⚠️ **CLI Scripts** - Optional, da meist single-use
5. ⚠️ **PDF Labels** - Falls PDF-Generator gefunden wird
6. ✅ **Popups** - Bereits implementiert!

## Zeitaufwand

- PHASE 3 (GUIs): 1.5h
- PHASE 4 (CLI): 1h
- PHASE 5 (PDF): 0.5h
- PHASE 6 (Popups): ✅ Bereits fertig!

**Gesamt:** ~3h (ohne Testing)
