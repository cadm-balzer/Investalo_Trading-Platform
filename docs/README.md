# Dokumentationswegweiser

| Dokument | Inhalt |
|---|---|
| [project-info.md](project-info.md) | Ursprünglicher Auftrag |
| [concept.md](concept.md) | Produkt, Umfang und End-to-End-Konzept |
| [implementation-brief.md](implementation-brief.md) | Bestätigter M1-Umfang und nächste Umsetzung |
| [runtime-pins.md](runtime-pins.md) | Verifizierte Versionen, Digests und Laufzeitnachweise |
| [architecture.md](architecture.md) | Module, Datenmodell, Schnittstellen und aktueller Stack |
| [trading.md](trading.md) | Strategieformalisation, Risiko, Backtests und Optimierung |
| [security.md](security.md) | Bedrohungen, Schutzmaßnahmen und Freigabekriterien |
| [operations.md](operations.md) | Deployment, Monitoring, Backup und Wiederanlauf |
| [deployment-plan.md](deployment-plan.md) | Compose/Authelia, öffentlicher HTTPS-Einstieg für Privatpilot und Recovery |
| [https-entry.md](https-entry.md) | Aktive freigegebene Let’s-Encrypt-Entwicklungsvorschau, Zugang und Rückfall |
| [mt5-bridge.md](mt5-bridge.md) | Ausgehende HTTPS-Bridge vom Heimnetzserver, Geräte-/Demo-Bindung und Abnahme |
| [bitget-connection.md](bitget-connection.md) | Eigene Nutzerkeys, Classic-Spot/Futures-Wallets und geschützte Einrichtung |
| [passkey-step-up.md](passkey-step-up.md) | Bestätigter Zusatzfaktor, Authelia-Faktorfrischebefund und Aktivierungsgates |
| [passkey-action-proofs.md](passkey-action-proofs.md) | Dauerhafter zielgebundener Nachweis, Vorschau-Bestätigung und getrennte OIDC-Claims |
| [passkey-browser-proof.md](passkey-browser-proof.md) | Ausdrücklich aktivierbare Browservorschau, vollständiger synthetischer BFF-Ablauf und Geräte-/Credentialgates |
| [passkey-credential-assertions.md](passkey-credential-assertions.md) | Isolierter TS-/Python-Assertionvertrag, ursprüngliche OIDC-Zeit und getrennte Passkey-/Autorisierungszeit |
| [passkey-credential-authorizations.md](passkey-credential-authorizations.md) | Geprüfte additive008 in der Fixture-DB, ausdrückliche Zweckfreigabe, globaler Einmalverbrauch und getrennte finale Locks |
| [inventory.md](inventory.md) | Host und Wiederverwendung der Referenzsysteme |
| [roadmap.md](roadmap.md) | Phasen, Abhängigkeiten und Abnahme |
| [tasks/board.md](tasks/board.md) | Git-basiertes Ticketsystem |
| [backlog.md](backlog.md) | Zurückgestellte Arbeit und Findungen |
| [interview.md](interview.md) | Entscheidungsbaum und Interviewrunden |
| [sources.md](sources.md) | Verifizierte offizielle Dokumentation |
| [memories/decision-log.md](memories/decision-log.md) | Entscheidungen und ihr Status |
| [memories/gotchas.md](memories/gotchas.md) | Technische Fallstricke |
| [Lokaler Start](../infra/README.md) | Compose, Operatorimport, Researchprofil und HTTPS-Abnahme |
| [Marktdaten](../packages/marketdata/README.md) | Snapshotvertrag, Coverage, CSV und öffentliche Bitget-Historie |
| [Credentialkern](../packages/credentials/README.md) | Gebundene AEAD-Envelopes, KEK-Rotation, lokale Restoretests und verbleibende Betriebsgates |
| [Credentialstore](../services/credentials/README.md) | DB-Bindung, Versionsprüfung, Rotation/Widerruf und einmalig autorisierte Bitget-Einrichtung |
| [Researchworker](../services/workers/README.md) | Tenantrolle, Leasing, Ergebnisvertrag und Health |

Anforderungen werden im Interview bestätigt. Das Konzept verweist auf vertiefende
Dokumente, statt Risiko- und Betriebsvorgaben mehrfach zu definieren.
