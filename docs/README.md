# Dokumentationswegweiser

| Dokument | Inhalt |
|---|---|
| [project-info.md](project-info.md) | Ursprünglicher Auftrag |
| [concept.md](concept.md) | Produkt, Umfang und End-to-End-Konzept |
| [implementation-brief.md](implementation-brief.md) | Bestätigter M1-Umfang und nächste Umsetzung |
| [runtime-pins.md](runtime-pins.md) | Verifizierte Versionen, Digests und Laufzeitnachweise |
| [architecture.md](architecture.md) | Module, Datenmodell, Schnittstellen und aktueller Stack |
| [paper-runner.md](paper-runner.md) | Inkrementeller Paperkern, Restore und Journalvertrag |
| [paper-postgres-store.md](paper-postgres-store.md) | Atomarer Checkpoint-/Journalwriter, eigene Kontorolle, Fixturemigration010 und nächste Feed-/Cockpitanbindung |
| [long-history-backtests.md](long-history-backtests.md) | Drei Jahre BTC/ETH-Forschung, reservierter Jahres-Holdout und nächste Paperausführung |
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
| [passkey-credential-execution.md](passkey-credential-execution.md) | PostgreSQL-geprüfter privater008-/003-Executor mit009-Abschlussaudit, Fixture-only009 und verbleibende Browser-/Betriebsgates |
| [passkey-credential-cockpit.md](passkey-credential-cockpit.md) | Private injizierte Cockpit-Orchestrierung, standardmäßig gesperrte008-API-Brücke und verbleibende Browser-/Schlüssel-/Brokergates |
| [passkey-credential-https.md](passkey-credential-https.md) | Privater Entwicklungs-HTTPS-Transport mit gegenseitigem TLS, unabhängigem Sitzungskontext und synthetischer Fixture |
| [credential-development-service.md](credential-development-service.md) | Getrennter synthetischer Credentialdienst mit eigener DB-/Schlüsselidentität, Startprüfung und administrativem Ergebnisaudit |
| [credential-asgi-transport.md](credential-asgi-transport.md) | Gepinnter ASGI-Unterbau des isolierten Credentialdiensts, mTLS-/Rawframing-/Frist- und Arbeitsslotgrenzen |
| [credential-browser-flow.md](credential-browser-flow.md) | Isolierter Eingabe-/Passkey-/Consentablauf mit begrenzten Fortsetzungen, privatem Seitenspeicher und synthetischer HTTPS-Prüfung |
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
