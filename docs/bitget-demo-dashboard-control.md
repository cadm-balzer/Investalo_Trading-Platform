# Demo-Steuerung im Dashboard

Stand 24.11.2026. PR125/main `a2f35c6` verifiziert. Ein eigener kleiner
Dashboard-Ablauf ersetzt den bisher dauerhaft deaktivierten Startbereich.
Keine neue Datenbanktabelle, Abhängigkeit, Exchange-Abfrage oder Orderroute.

## Bedienung

Unter der vorhandenen H1-RSI-Tabelle werden Coin-Kandidaten und die Obergrenze
von 3–7 gleichzeitigen Baskets ausgewählt. Initial: drei Baskets, sieben
bekannte Kandidaten; die Empfehlung gilt für den ersten Demo-Lauf.
Die Kandidatenzahl bedeutet keine zusätzliche Kapitalzuordnung.
Profil bleibt Long/H1/2×/isoliert, fünf automatische Käufe und die manuelle
sechste Stufe. Stufenbeträge sind Eigenkapital-Margin.

„Demo-Start anfordern“ speichert einen Startwunsch samt Einstellungen.
„Pausieren“ pausiert diesen Wunsch und behält die zuvor gespeicherten
Einstellungen; nicht gespeicherte Checkboxänderungen können Pause nicht
verhindern. Bestehende Positionen werden dadurch nicht geschlossen.
Ein künftig installierter Worker muss Pause vor neuen Käufen prüfen und
die nötige Verwaltung bereits offener Baskets separat fortführen.

Die Anzeige lautet ausdrücklich „Start angefordert“, nicht „Handel aktiv“.
`worker_state=not_installed` und `execution_enabled=false` sind verbindlich.
Diese Implementierung installiert keinen Worker und erteilt keine native
Orderfreigabe. Native Zulassung, aktuelle Kapitalbasis, eigener ursprünglicher
Strategie-Consumer und H1-Worker bleiben in Umsetzung. Der technische BTC-Test
und seine Freigaben werden nicht wiederverwendet.

## Speicherung und Zugriff

`GET/POST /api/bitget-demo/control` verwenden die originale aktuelle
Cockpit-Session, die bestehende private Pilotidentität, die aktuelle
API-Rolle Owner/Trader und aktive Trading-Metadaten. Tenant, Konto, Benutzer,
Subject, Auth-Epoch, Connection und Credential-/Storageversion binden den
Wunsch. Wechsel eines dieser Merkmale macht einen alten Start ungültig.
Sessionhandle und Sessionwerte werden vor den Awaits eingefroren.

POST prüft Browser-Origin, Same-Origin, CSRF, JSON und den festen Pfad;
der interne Next-Origin hinter Caddy ist kein öffentlicher Browser-Origin.
Begrenzter Intake wird wiederverwendet. Aktuelle Berechtigung/Installation/
Verbindung werden vor Veröffentlichung und vor HTTP-Erfolg erneut geprüft.
Es wird kein vorhandener Read-, Key- oder technischer Market-Token erweitert.

Der einzelne Cockpitprozess schreibt im separaten privaten Unterverzeichnis
`COCKPIT_STATE_DIR/demo-h1-control`. Pro Tenant/Konto eine signierte Datei,
700-Verzeichnis/600-Datei/eigener UID, NOFOLLOW/nlink-/Größenkontrolle,
exklusive temporäre Datei, fsync, atomarer Rename, Verzeichnis-fsync und
exakter Readback. Eine eigene HMAC-Domäne wird vom bestehenden Sessionsecret
abgeleitet; keine neuen operatorseitigen Schlüssel erforderlich.
Keine Brokerdaten, OIDC-Tokens, Sessionhandles oder CSRF-Werte werden gespeichert.
Keine UID-/Connection-/Keyversionen erscheinen im Browserstatus.

Versionsvergleich und ein gemeinsamer Writer verhindern stale/parallel
überschriebene Wünsche. Nach unbestätigter POST-Antwort bietet der Browser
nur Statusabruf; kein automatischer Schreibretry. Ein bereits gespeicherter
Wunsch kann über GET nachgelesen werden. Dies ist eine Einzelprozessinstallation,
keine Unterstützung für mehrere gleichzeitige Cockpit-Writer.

## Prüfung und Rollout

11 neue Fälle mit tatsächlicher privater Datei-/Signatur-/Restartprüfung
und tatsächlichem BFF-Handler über synthetische Session-/API-/Identityports.
41 betroffene gepinnte Nodefälle grün einschließlich RSI-/Konto-/SSR-
Regression; volle Typprüfung und finaler gepinnter Cockpitbuild grün.
Tatsächlicher Next-GET/POST der verpackten Route verweigert Zugriff bei
Default-off ohne Netz, Quellcode- oder Credentialmounts.
Lesender Audit bestätigt unveränderte Originaldateihashes, alle sieben
laufenden Dienste/Images und den technischen Testjournalstand8.
Kein tatsächlicher Brokerrequest oder Deployment.

Eigenes Opt-in `COCKPIT_DEMO_H1_CONTROL`, standardmäßig aus.
`infra/compose.demo-h1-control.yaml` aktiviert ausschließlich diese
Dashboard-Steuerung. Bei einem Rollout zusätzlich zu allen sechs bestehenden
Overlays verwenden und anschließend erhalten. Der bisherige technische
Testjournalstand8, Credentials und Services werden durch die lokale
Implementierung nicht verändert.
