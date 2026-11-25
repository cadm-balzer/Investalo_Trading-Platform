# Dauerhafte Demo-Startfreigabe

Stand 25.11.2026. PR128/main`0d07c13` verifiziert. Der Nutzer autorisiert
automatischen Demohandel und bestätigt im ursprünglichen Dashboard
„Start angefordert“, Revision1, 25.11.2026 13:20:31 CET:
sieben Kandidaten, Basketobergrenze3, festes2×-Profil.

`DurableBasketConsumer` verifiziert unveränderte HMAC-Payloadbytes des
vorhandenen Dashboard-Start-/Pausevertrags. Originalzeit, Actor, Konto,
Connection und Keyversion bleiben gebunden. Eigene private Dateien mit
PID-/Inode-/Modusprüfung, Prozessmutex/flock, exklusiven Ausgabedateien,
fsync und Readback. Ein monotoner Kontrollstand mit unveränderlichen
Akzeptanzmarken verhindert alten Start nach Pause, auch bei verlorenem
Checkpoint vor der ersten Order. Ungewisse Schreibvorgänge bleiben gesperrt.

Freigaben betreffen genau die aktuelle originale Journalvorbereitung,
Receipt, Grid, Menge, Stufe und Command-ID. Dispatcher und Consumer verwenden
denselben Intentdecoder. Ein dauerhafter Commandverbrauch erfolgt vor
Schlüsselzugriff und POST; ACK-Verlust/Neustart erzeugt keine neue Freigabe.
Pause sperrt Käufe; belegte eigene Reduce-only-Ausstiege bleiben zulässig.
Eine Kontrolländerung während des Verbrauchs sperrt Veröffentlichung.
Bereits verbrauchte, aber unversandte Vorbereitungen dürfen nicht wieder
verwendet werden; ein späterer Worker muss diese journalgerecht abbrechen.

`DemoWorkerCredentialStore` ist ein eigener Read-only-Adapter über020.
Er verwendet keine erfundenen OIDC-Zeiten und verlängert keine Browsersitzung.
Das originale autorisierte Startdatum bleibt erhalten; die private
Credentiallease gilt höchstens60s. Tatsächlicher eingeschränkter LOGIN,
aktuelle Mitgliedschaft/Actor/Subject/Issuer/Epoch/reauth_after, Konto,
Trading-Purpose, native Bindung und unveränderte Keyversion werden erneut
geprüft. Der vorhandene Trading-AEAD-Decoder/Provider wird wiederverwendet.
Der Adapter hat keine Register-/Rewrap-/Revokeoperation.

`DemoWorkerStartProbe` verbindet den echten signierten Auftrag über diesen
SQL-/AEAD-Pfad mit den bestehenden drei nativen GETs. Die verpackte,
standardmäßig ausgeschaltete CLI setzt keine Orders oder Kontoeinstellungen,
erstellt kein Finanzjournal und installiert keinen dauerhaften Handelsloop.

## Freigegebene Demo-Ausnahme

Der Nutzer bestätigt am25.11.2026 ausdrücklich für automatische Demo-Baskets:
fehlendes Bonusfeld, fehlende native Market-Höchstmenge, vorab unbekannte
tatsächliche Kosten sowie ältere Orderhistorie außerhalb des API-Fensters
dürfen akzeptiert werden. Basketbudgets,2×,isolierte Longs, aktuelle
Konto-/Orderprüfungen und kein erneuter unbestätigter POST bleiben verbindlich.
Echtgeld bleibt aus. Dies ist eine neue Strategie-Ausnahme; der technische
20USDT-Testvertrag wird nicht als Strategiegrößenregel verwendet.

`ApprovedDemoStrategyPolicy` bindet diese Entscheidung an das konkrete
Demokonto und die aktuelle Keyversion. Der Startparser akzeptiert damit
ausschließlich fehlendes `grant`; der Wert bleibt unbekannt. Positive
bekannte Sicherheiten, fehlende andere Felder, fremde Positionen oder
abweichende Salden bleiben Blocker. Quellenhash und Ergebnis binden den
Policyhash. Ohne diese installierte Policy bleibt der Parser strikt.

Die native Marketgrid-/Margin-/Fundingzulassung muss diese neue Policy
noch ausdrücklich übernehmen. Ein Policyobjekt ist keine Orderfreigabe.

## Prüfung und tatsächlicher Betrieb

151 betroffene gepinnte Fälle grün:84 native/Consumer/Journalfälle und67
tatsächliche PostgreSQL-/AEADfälle;32 neue Fälle. Finaler Executorbuild
und sechs verpackte Quellhashes geprüft.

020 wurde nach isoliertem Rollbackpreflight und Fixturetests unter der
autorisierten Startvorbereitung produktiv installiert. Original001–019
Checksums verifiziert, private vollständige Datenbanksicherung davor.
Sieben Dienste/Images, ursprüngliche privaten Datei-Hashes und technisches
BTC-Journal Revision8 unverändert. Keine neue Order oder Grantverbrauch.

Erster tatsächlicher eingeschränkter Worker-LOGIN/AEAD/Nativeabruf mit
originalem Start1: `grant` fehlt, strikt `collateral_unconfirmed`.
Nach ausdrücklicher Freigabe und verpacktem Policyabruf:
25.11.2026 12:36:55.818UTC, keine Startkontoblocker, native Equity
9.999,91047862USDT und Flat-Kontobeleg bestätigt. `grant` bleibt unbekannt.
Dieser aktuelle Betrag ersetzt keine historischen Guthaben und ist kein
Strategieprofitnachweis.

Private Originalauftrag-/Policy-/Quellen-/Image-/Hashreceipts und Backup:
`infra/local/demo-h1-worker/start-inspect-*`. Nur getrennte signierte
Auftragskopie und abgeleiteter Intentkey in einer vorübergehenden,
schreibgeschützten UID10003-Installation; kein Mount aller Cockpit-Sessions.
Originaler Dashboardauftrag vor und nach den GETs identisch geprüft.

**Automatischer Demohandel ist noch nicht aktiv.** Der kontinuierliche
H1-Worker, operative Kontrollübergabe/Heartbeat und vollständige native
Strategiegrid-/Margin-/Fundingzulassung bleiben in Umsetzung. Der aktuelle
Dashboardzustand `worker_state=not_installed` bleibt korrekt.
