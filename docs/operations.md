# Betrieb, Deployment und Wiederherstellung

Stand 2026-11-07. Bestätigt: vorhandenen Server nutzen, zunächst kostenlose
externe Dienste/Accounts; TradingView Essentials besteht bereits.
Q31 bestätigt die lokale Umsetzung. Docker ist installiert; fünf lokale
Compose-Dienste laufen über einen einzigen Loopback-HTTPS-Port.
Host-SSH und DNS wurden nicht verändert. Docker verwaltet seine lokalen
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
DNS und `cockpit.investalo.de` werden erst mit konkret freigegebener
Pilot-/Produktionskonfiguration aktiviert.

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

**Verbindungsausfall:** Neue Exposition stoppen, brokerseitigen Schutzstatus
prüfen, reconnect/reconcile, danach Risk Gate erneut.

**Riskverletzung:** Nach bestätigter Policy Einstiege sperren, Orders stornieren
oder Positionen reduzieren/schließen. Aktionen getrennt auditieren.
Die Policy darf keine Schutzmaßnahme auf eine AI-Antwort verschieben.

**Schlüsselkompromittierung:** Betroffene Verbindung sperren, Key widerrufen,
Zugriffe prüfen, neuen Key minimal berechtigen, Accountzustand reconciliieren.

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
