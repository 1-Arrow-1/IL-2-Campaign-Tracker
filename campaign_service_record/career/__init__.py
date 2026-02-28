"""
Career module: read-only access to IL-2 Career Mode data from cp.db.

Provides:
    CareerDatabase        -- sqlite3 read-only wrapper for cp.db
    PilotDescriptionParser -- parses pilot.description long string
    CareerChainResolver   -- resolves career.extends chains into VirtualPilotCareer
    StatisticsMapper      -- maps pilot table kill counters to combat_results shape
    MissionReportLinker   -- 3-step missionReport file matching
    CareerAggregator      -- transforms cp.db data into API response shapes
"""
