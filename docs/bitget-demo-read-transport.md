# Getrennter Classic-Demo-Lesezugang

Stand 2026-11-15, IP-015/IP-016. PR76 (`0c0df27`) ist in
`main5db8f43` enthalten; GitHub/Fetch/Ancestry bestätigt.

`futures_demo_read.py` verbindet den [registrierten Outboxzugang](bitget-demo-account-registry.md)
mit einem getrennten signierten Demo-GET-Transport und dem vorhandenen
[14-Achsen-Accountcheck](bitget-demo-account-check.md). Keine Orders,
Modeänderungen, Cancel, Transfers, Livefallbacks oder Dienstaktivierung.

## Feste signierte Requests

`SignedDemoReadRequest` erlaubt nur die Classic-Identityabfrage
`GET /api/v2/spot/account/info` und die ursprünglichen 14 Accountcheckbereiche
mit deren begrenzten nativen Cursors. Host ist ausschließlich
`https://api.bitget.com`; Header `paptrading: 1` ist zwingend.
Keine frei wählbare URL, Methoden-/Bodyparameter, Spotwallet- oder
Order-/Fundingpfade. HMAC umfasst exakt Timestamp, GET und den gesendeten
Pfad inklusive der unveränderten Queryreihenfolge.

Requests, Credentials und Header bleiben unveränderlich, redigiert und
gegen Serialisierung geschützt. Der vorhandene Classic-Readclient und seine
drei erlaubten GET-Pfade bleiben unverändert; sein Transport lehnt die neuen
Demo-Requests ab. Der Demo-Transport akzeptiert umgekehrt keine Realkonto-
Requests.

`HTTPSDemoReadTransport` wird nur ausdrücklich ausgewählt. CA/Hostnameprüfung,
TLS mindestens 1.2, keine Umgebungsproxies, kein Redirect, maximal 1 MiB je
Antwort und 1–5 Sekunden Requesttimeout. Fehlercodes sind statisch; keine
Providertexte oder heimlichen Wiederholungen. Maximal 60 Antworten inklusive
Identity; ursprüngliche Paginationgrenzen bleiben erhalten.

## Provider und Originalbindung

`DemoReadCredential` ist eine **vertrauenswürdige Providerdeklaration**, kein
nativer Nachweis, dass ein Key tatsächlich im Demo-Modus erstellt wurde.
Sie enthält die ursprüngliche DemoBinding/Credentialreferenz, eine private
Credentialtriple, bekannten Parent, kanonische Egress-IP, unveränderlichen
Provenienzbelegdigest, positive Revision und Ablaufuhr.

Der explizit injizierte geschützte Provider muss die deklarierte Provenienz
tatsächlich prüfen und nur dieses eigene Demo-Leseprofil bereitstellen.
Ein normaler Credentialstoreeintrag darf nicht allein durch Setzen des Headers
in einen Demo-Key umgedeutet werden. Dieser Checkpoint implementiert weder
diesen Provider noch eine neue echte Keyeingabe oder DB-Profilmigration.
Deklarierte Parameter allein sind kein Einrichtungs-/MFA-/Rechtebeweis.

`DemoReadClient.capture` akzeptiert ausschließlich `RegisteredDemoOutbox`.
Vor dem Laden von Secrets oder dem ersten Request werden Owner, vollständige
Originalbinding, aktueller Katalog und Outboxrevision geprüft. Der Provider
wird vor und nach jedem GET erneut geprüft: gleiche Binding/Revision/
Provenienz/Parent/IP/Ablaufzeit und gleiche tatsächliche Credentialtriple.
Der verbleibende deklarierte Zeitraum muss positiv und höchstens 60 Sekunden
sein. Änderungen verwerfen den gesamten Abruf, ohne Ersatzkey oder Wiederholung.

## Native Identity und Accountcheck

Die erste Antwort muss das bestehende Classic-V2-Leseschema mit ursprünglicher
UID und genau dem erwarteten Parent bestätigen. Die IP-Whitelist muss exakt
die eine konfigurierte Egress-IP enthalten. Nur die bestehende bekannte
Read-only-Rechtevokabel ist erlaubt; `coor` und `cpor` müssen vorhanden sein.
Unbekannte/Schreibrechte werden nicht als Leseprofil normalisiert. Ein späteres
Demo-Tradingkeyprofil benötigt einen eigenen geprüften Vertrag.

Erst danach werden Wallet, Positionen, beide regulären Pendingstatus,
drei Triggerfamilien und sieben Konfigurationen gelesen. Cursorfolge,
Quellenfrische und sämtliche vorhandenen Accountdiagnosen bleiben wirksam.
Initialer Journalreceipt muss bis zur Ergebnisprüfung exakt aktuell bleiben.
Fehler, fehlende Rechte, veränderte Registry, abgelaufene/bewegte Uhren,
veränderte Providerdaten oder Journalrevision liefern keinen neuen Bericht.
Der Abruf erzeugt keine Journal-, Cash- oder Basketbuchung.

Gesamter Abruf und native Identity-/Antwortfrische bleiben auf die bestehenden
5 Sekunden begrenzt. Diese Grenze wird nicht verlängert, um eine langsame
Verbindung erfolgreich erscheinen zu lassen. Identity wird pro Clientinstanz
höchstens einmal pro Sekunde gestartet; tatsächliche gemeinsame UID-Quota und
Betriebslatenz benötigen eigene Abnahme.

`DemoReadResult` enthält den privaten Accountbericht, geprüfte Identity,
ursprünglichen Identityantwort-SHA256, Providerdeklarationsdigest und Revision.
Keine rohe Antwortpersistenz. `native_acceptance_verified` bleibt false;
Accountcheck-Execution-/Ledger-/Orderscope-Freigaben bleiben ebenfalls false.

## Abnahme und nächster Schritt

22 neue synthetische Provider-/Antwort-/nachgebildete HTTPS-Fälle plus
121 bestehende: **143 grün** auf Host-Python 3.14.4.
Tatsächliche private registrierte Outbox/CAS, signierte Querybytes, 15 Requests/
native Cursor, UID/Parent/IP/Rechte, Provider-/Journalwechsel, Frische, TLS/
Proxy/Redirect/Timeout/Antwortgröße, Fehlerredaktion und fehlende Retries geprüft.
Keine echten Credentials oder privaten Brokerrequests verwendet.

Die offizielle [Classic-Demo-Dokumentation](https://www.bitget.com/docs/classic/demo-trading/rest-api)
(geprüft 2026-11-15) verlangt einen gesondert im Demo-Modus erstellten Key und
`paptrading: 1`. Sie beweist noch keine tatsächliche Antwort-/Identityabdeckung
dieses konkreten eigenen Kontos. Unsupported/Mismatch bleibt Fehler; kein
Realkontofallback. Echte Provider-/Provenienzbindung, native Endpoint-/Latenz-
Abnahme, ältere Orderscope- und tatsächliche Kosten-/Fundingquelle folgen.
Keine Services/DB/Migration/Dependencies/Backtests/Public/Live/AI-Aktivierung.
