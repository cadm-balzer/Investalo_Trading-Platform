# Betrieb, Deployment und Wiederherstellung

Stand 2026-11-08. Bestätigt: vorhandenen Server nutzen, zunächst kostenlose
externe Dienste/Accounts; TradingView Essentials besteht bereits.
Q31 bestätigt die lokale Umsetzung. Docker ist installiert; fünf Basisdienste
und ein optionaler Offline-Researchworker laufen über Compose. Die ausdrücklich
freigegebene Entwicklungsvorschau veröffentlicht ausschließlich Caddy auf
`5.45.96.83:80/443`; das Standardprofil bleibt auf Loopback8443.
Der Nutzer hat DNS eingerichtet; Host-SSH blieb unverändert. Docker verwaltet seine lokalen
Netzregeln. Öffentliche Pilot-/Produktionsfreigabe bleibt separat.
Start und Grenzen: [infra/README.md](../infra/README.md).

## Umgebungen und Ressourcen

Development, Paper/Demo und später Live haben getrennte Konfigurationen,
Identitäten, Schlüssel und Daten. Der initiale Host hat 2 vCPU und 1,9 GiB RAM
ohne Swap. Gleichzeitig große Backtests, Next.js-Builds und Liveausführung
sind darauf kein belastbarer Produktionsplan.

Lesender Echtgeldzugang ist von Ausführungsrechten getrennt: M1-Realkontokeys
sind read-only, Paper simuliert lokal, Demo sendet nur an getrennte Demokonten.
Der Server verweigert Echtgeld-Dispatch bis zur expliziten Livefreigabe.

Vorschlag: Builds und Backtests begrenzen/serialisieren, Liveprozesse später
mit garantierten Ressourcen, Research bei Bedarf auslagern. Eine Erweiterung
auf beispielsweise 4–8 GiB RAM ist eine Kapazitätsempfehlung, keine bereits
genehmigte Beschaffung oder ausreichende HA-Lösung.
Konkrete Mindestwerte werden anhand eines repräsentativen Lasttests festgelegt.

Der Einzelserver ist ein Single Point of Failure. Brokerseitige Schutzorders
und eine autonome MT5-Bridge können Risiken reduzieren; sie ersetzen kein HA.

## Bereitstellung

Q13 bestätigt Docker Engine mit Compose von Beginn an.
Runtimeversionen exakt pinnen, Images mit Digest, Lockdateien und reproduzierbarem
Build. Serviceidentitäten von Root und voneinander trennen.
Keine privilegierten Container oder Docker-Socket-Mounts, interne Ports nicht
öffentlich publishen. Externe Erreichbarkeit ausdrücklich prüfen, da Docker
veröffentlichte Ports Hostfirewallregeln umgehen können.

Ein zentraler Reverse Proxy/TLS-Einstieg. Q20 plant ihn öffentlich schon für
den eingeladenen Privatpilot; keine öffentliche Registrierung.
Datenbank und interne Dienste ausschließlich lokal/intern.
Für die freigegebene Vorschau ist `cockpit.investalo.de` bereits aktiv.
Laufende Edge-/Anwendungsdienste mit
`bash infra/scripts/compose.sh --file infra/compose.public-preview.yaml …`
bedienen. Ohne Overlay werden lokale Ports/Origins wiederhergestellt.
Geschützten ACME-Zustand persistent halten; Proxyneustart und Zertifikatsvertrauen
sind geprüft. Erneuerung, Ablaufüberwachung und externe Wiederherstellung bleiben
BL-026. [Zugang und Rückfall](https-entry.md).

Die IP-037-Nachweisvorschau ist nur mit `COCKPIT_PASSKEY_PROOF_PREVIEW=1`
aktivierbar. Standard- und öffentliches Composeprofil lassen sie ausgeschaltet;
laufende Vorschaucontainer wurden für diesen Checkpoint nicht verändert.
90 tatsächliche HTTPS/BFF/API/PG-Prüfpunkte liefen isoliert mit eigenen
Testsecrets, synthetischer P256-Registrierung/Ticketattestierung und Fixture-DB.
Neun Prüfungen mit ausgeschalteter Vorschau bestätigten ausbleibende Faktor-/
Nachweismutationen. Öffentliche Aktivierung, reale Geräte-/E-Mail-Abnahme und
Credentialintegration folgen separat. [Prüfablauf](passkey-browser-proof.md).
IP-038 ergänzt den isolierten Passkey-Credentialassertionvertrag.
Er hat keinen HTTP-/Transport-/Schlüsselprovideranschluss. Bestehende Runtime- und
Compose-Dienste bleiben unverändert; das neue optionale Offlineprüfprofil
`credential-assertion-checks` hat kein Netzwerk, Secrets oder DB-Abhängigkeiten.
Signaturprüfung
ist kein Replayverbrauch; vor späterer Probe sind zweckgebundene dauerhafte
Freigabe und Abgleich bei unbekanntem Commit erforderlich.
[Integrationsgrenzen](passkey-credential-assertions.md).
IP-039 ergänzt additive008 und den privaten Consume-/Lockclient. Nach geprüftem,
vollständig zurückgerolltem DDL-/Runtime-Prepare-Preflight ist008 ausschließlich
in `investalo_credentials_checks` angewendet; `investalo` bleibt001–007.
Gepinnte Migrate-/Storage-/API-Prüfbuilds und 461 erneut ausgeführte tatsächliche
API-/Workerchecks sowie 271 Credentialtests (157 tatsächliche PostgreSQL-Fälle)
bestanden.008 ist in der Fixture-DB checksumgeschützt und immutable.
Die sechs öffentlichen Container bleiben unverändert und gesund;
öffentlicher HTTPS-Lesecheck200 mit regulärer TLS-Prüfung bestanden,
Nachweisflag weiterhin aus. Ein unbekannter Consumecommit liefert keinen
Handle; vor erneutem Versuch autoritativen Zustand abgleichen. Der getrennte
finale Lock führt selbst keine Credentialmutation oder Brokerprobe aus.
[Dauerhafte Autorisierung](passkey-credential-authorizations.md).

Deploymentablauf: geprüfter Code/Lockstand → Build/Artefakt →
relevante Tests → verschlüsselte Sicherung → Migration mit Rückfallplanung →
private Paperprüfung → explizite Produktionsfreigabe → kontrollierter Rollout.
Echte Handelsaktivierung ist zusätzlich konto-/strategiebezogen freizugeben.

Keine neue CI/CD-Toolabhängigkeit wurde eingeführt. Git-basiertes lokales
Ticketboard und manuelle geprüfte Abläufe genügen für die aktuelle lokale Entwicklung.
Ein späteres automatisiertes Releaseverfahren wird konkret vorgeschlagen.

## Gesundheits- und Fachmetriken

Compose-/Authelia-Serviceplan mit öffentlichem Pilotzugang und bestätigtem Recoveryablauf:
[deployment-plan.md](deployment-plan.md).

| Signal | Reaktion / Zweck |
|---|---|
| API-Verfügbarkeit und Authfehler | Produktstörung versus möglicher Missbrauch unterscheiden |
| Datenalter/Lücken | Neue Exposition bei ungültiger Signalgrundlage sperren |
| Job-/Signallatenz | Backtests nicht zulasten des Handelspfads |
| Bridgeheartbeat und Clock Drift | Konto-/Zeitfehler früh erkennen |
| `UNKNOWN`-Orders und Positionsabweichung | Sofortiger Abgleich, keine blinden Wiederholungen |
| Equity/Margin/Risklimits | Kontinuierliche Grenzprüfung, nicht nur bei Kerzenschluss |
| Backup-/WALalter und Restores | Wiederherstellbarkeit nachweisen |
| Secretzugriffe und Rotation | Unerwartete Zugriffe erkennen |
| Disk/RAM/CPU | Ressourcenerschöpfung und Datenverlust verhindern |

Structured Logs tragen Correlation-, Tenant- und Accountreferenzen in
minimierter Form, ohne Credentials oder unnötige Personendaten.
Alarmierungsdienst und Empfänger werden separat gewählt; es werden keine
externen Nachrichten oder Accounts ohne Freigabe eingerichtet.

Der Researchworker hat 192 MiB/0,3 CPU als lokale Grenze und ein eigenes Profil.
Sein Healthcheck verlangt aktuellen erfolgreichen DB-/Heartbeatfortschritt.
Leaseverlust verwirft Ergebnisse; höchstens drei Attempts, danach sichtbarer
Fehler. Das ist kein Brokerretryverfahren. Datasetimport erfolgt separat mit
Operator-/Migrationsidentität, niemals durch den Researchworker.
Ein 90-Tage-Lauf prüft Funktion; Dreijahreslast, Retention und Mehrnutzerlast
sind vor dem Pilot gesondert zu messen.

Q27 bestätigt für den Paper-/Demopilot RPO 24 Stunden und RTO vier Stunden
als Planungsziele, mit täglicher verschlüsselter externer Sicherung, zusätzlicher
geschützter Offlinekopie und getrennter Schlüsselaufbewahrung.
Das konkrete kostenlose Ziel und ein Restoretest sind vor Pilotfreigabe
erforderlich. Weitere SLOs wie Kontoaktualisierung werden anhand der
Brokerfähigkeit und Hostmessung konkretisiert. Kein bereits nachgewiesenes
SLO und keine Echtgeldfreigabe.

## Backups und Disaster Recovery

PostgreSQL-Basebackup plus WAL-Archivierung ist für PITR vorgeschlagen.
`pg_dump` allein ermöglicht kein WAL-basiertes PITR.
Verschlüsselte externe Kopie mit getrennten Rechten/Retention ist für ernsthaften
Betrieb notwendig; kostenlose Speichermöglichkeiten und Schlüsselwiederherstellung
sind noch zu klären. Eine zweite Kopie auf derselben VM ist kein Disaster Recovery.
Runtime und Backupwriter dürfen geschützte ältere Generationen nicht löschen.
Mindestens eine unveränderbare oder offline getrennte Kopie und unabhängig
verwaltete Löschrechte vorsehen. Verschlüsselung verhindert keine Löschung.
Wenn Free-Angebote diese Grenze nicht ermöglichen, bleibt das eine offene
Betriebsentscheidung vor Livefreigabe.

Zu sichern: Fachdaten, Fill-/Commandjournale, Strategie-/Riskversionen,
Konfiguration, erforderliche Schlüsselreferenzen und reproduzierbare Artefakte.
Keine rohen Brokerkeys in Logs oder unverschlüsselten Archiven.
Regelmäßig Restore in isolierter Umgebung mit geprüftem Ergebnis durchführen.

**Wiederanlauf nach Restore:**

1. Execution und Scheduler deaktiviert lassen.
2. Daten-/Schema-/Schlüsselstand und Konto-/Bridgeidentitäten verifizieren.
3. Brokerorders, Fills, Positionen und Cashflows seit dem Restorepunkt abgleichen.
4. Alte Intents/Leases und ungeklärte Commands explizit behandeln; keine Replayorders.
5. Risklimits, Schutzorders und Datenfrische prüfen.
6. Lesenden/Paperbetrieb testen; Live erst nach dokumentierter Wiederfreigabe.

Ein Datenbankrollback setzt ausgeführte Trades nicht zurück.

## Störungsabläufe

**Öffentlicher HTTPS-Zugang:** Zuerst DNS, tatsächliche Listener und TLS-
Terminierung prüfen. Lokales CA-Zertifikat und `auto_https off` sind keine
öffentliche ACME-Konfiguration. Domainwechsel erfordert abgestimmte
OIDC-/Cookie-/RP-Werte und bewusste Issuer-Nutzerbindung.
[Aktive Entwicklungsvorschau und Rückfall](https-entry.md).

**Verbindungsausfall:** Neue Exposition stoppen, brokerseitigen Schutzstatus
prüfen, reconnect/reconcile, danach Risk Gate erneut.

**Riskverletzung:** Nach bestätigter Policy Einstiege sperren, Orders stornieren
oder Positionen reduzieren/schließen. Aktionen getrennt auditieren.
Die Policy darf keine Schutzmaßnahme auf eine AI-Antwort verschieben.

**Schlüsselkompromittierung:** Betroffene Verbindung sperren, Key widerrufen,
Zugriffe prüfen, neuen Key minimal berechtigen, Accountzustand reconciliieren.

**Passkeywiderruf:** Nach manuell bestätigter E-Mail über den Migrationsoperator
mit aktueller Speicherversion widerrufen. Dabei werden alle Tenant-Sitzungen
des Nutzers ungültig; Registry und Credential-ID bleiben terminal reserviert.
Ersatz-/Recoveryweg ist noch offen. Unbekannte Commits vor Wiederholung
abgleichen. [Lokale Bedienung](../infra/README.md#passkey-enrollment-und-widerruf).

**Interner Aktionsnachweis007:** Claim, Kryptoprüfung und Bestätigung haben
dauerhafte Einmalzustände. Bei Crash oder unbekannter Commitantwort den
gespeicherten Zustand und Audit abgleichen; keinen verbrauchten Versuch
wieder freigeben. Die ausdrücklich aktivierbare Browservorschau bestätigt
ausschließlich den Nachweis mit `execution_enabled:false`;
Credentialausführung bleibt gesperrt.
[Ablauf und Grenzen](passkey-action-proofs.md).

**Migration vom Altsystem:** Ein Writer je Konto, offene Commands/Fills abgleichen,
Shadowvergleich, alten Writer deaktivieren, neuen begrenzt freigeben.
Rollback ebenfalls mit Brokerabgleich; kein paralleles Steuern.

## Kosten und Wartung

Zunächst Free-Angebote nutzen, ihre Minuten-/Tagesquoten, Speicherlimits,
Verfügbarkeit, Datenschutz und Nutzungsrechte dokumentieren.
Ein Free-Angebot ohne ausreichende Security-/Datenrechte wird nicht zur
Livevoraussetzung erklärt. Bei einer Lücke bleibt das betroffene Feature
deaktiviert, bis eine tragfähige Lösung bestätigt ist.

Regelmäßig: Sicherheitsupdates kontrolliert übernehmen, Abhängigkeiten und
API-/Brokeränderungen prüfen, Schlüssel rotieren, Restore testen, Journal und
Risikoprofile abstimmen. Takt und Verantwortlichkeit folgen dem Interview.
