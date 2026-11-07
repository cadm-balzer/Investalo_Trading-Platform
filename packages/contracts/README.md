# Versionierte Verträge

Versionierte API-, Job-, Event- und MT5-Bridgeverträge. Tenant-/Kontobindung,
Command-ID, Ablaufzeit, Strategie- und Risikoprofilversion sind explizit.
Implementiert sind `marketdata-snapshot/1` und `backtest-result/1` mit
strenger API-/Worker-/Cockpitvalidierung. Die Strategie bleibt
`crypto-basket/1.0.0`. JSONzahlen für Geld/Preise sind kanonische Dezimalstrings;
Tenantbezug, Daten-/Konfigurations-/Kostenhash und Forschungsstatus sind explizit.

Die konkreten Implementierungen liegen bei [Marktdaten](../marketdata/README.md),
[API](../../services/api/README.md) und [Worker](../../services/workers/README.md).
Gemeinsame generierte Export-/Event-/Bridge-Schemas folgen bei konkretem Bedarf.
Details: [Architektur](../../docs/architecture.md).
