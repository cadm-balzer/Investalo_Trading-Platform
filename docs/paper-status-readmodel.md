# Gespeicherter Paperstatus und Handelsjournal

IP-051,2026-11-09: API und Cockpit können den bestätigten Paperstand des
angemeldeten Tenants anzeigen. Öffentliche Dienste wurden nicht neu erstellt;
die Anzeige ist standardmäßig ausgeschaltet. Ein eingerichtetes Konto oder
ein gespeicherter Input belegt keinen laufenden Worker.

## Vertrag und Zugriff

`GET /v1/paper-status` benötigt die bestehende signierte API-Authentifizierung
und `API_PAPER_STATUS_PREVIEW=1`; ausgeschaltet antwortet die Route mit404,
ohne Paperdatenbankzugriff. Der Cockpit-Server benötigt unabhängig
`COCKPIT_PAPER_STATUS_PREVIEW=1`. Beide Flags fehlen im Default Compose und
in der öffentlichen Vorschau. Keine Browserroute zur Paperänderung.

Additive011 stellt `platform.paper_status_rows(epoch, original_auth_time)`
bereit. Ausschließlich der eingeschränkte `investalo_runtime`-LOGIN darf die
Funktion ausführen. Aktiver Nutzer, aktueller Epoch, ursprüngliche
OIDC-Identität/-Zeit und aktive Tenantmitgliedschaft werden geprüft und
gesperrt; auch Viewer dürfen eigene Paperdaten lesen. SQL vertraut der
API-Assertionprüfung und den transaktionslokalen Identitäts-GUCs. Diese GUCs
sind kein unabhängiger Signaturnachweis.

Maximal20 eigene Bitget-Paperkonten in USDT und je20 letzte bestätigte
Journalinputs. Keine direkten Tabellen- oder Writerrechte für Runtime;
bestehende FORCE-RLS und die Paper-LOGIN-Bindung bleiben erhalten. Die Funktion
projiziert den vom vertrauenswürdigen Writer gespeicherten Checkpoint und
prüft dessen SHA256. Die API validiert zusätzlich Actor/Konto, BTC/ETH,
höchstens sechs Einstiege je Asset, Zahlen, Zeitpunkte und Journalrevisionen.
Sie liefert ausschließlich `paper-status/1`: keine Rohcheckpoints,
Orderreferenzen, Freitextgründe, manuellen Freigaben oder Credentials.
Journalmeldungen stammen aus einer festen deutschen Liste.

## Anzeige

Übersicht, Portfolio und Journal erhalten dasselbe Paperpanel. Cash und
Equity stehen je Konto in USDT. Gehaltene Mengen werden mit dem gespeicherten
Bid bewertet; nach30 Sekunden ist die Bewertung ausdrücklich historisch.
Fehlt ein erforderlicher Kurs, ist Equity nicht bewertbar. Ohne Positionen
entspricht Equity dem Cash. Ein ungestartetes Konto bekommt keine erfundene
10.000-USDT-Bilanz.

Letzter gespeicherter Input und Revision zeigen den bestätigten Datenstand.
Fehlende aktuelle Tagesbasis und Riskhalt zeigen die Kaufsperre. Mengen,
Durchschnittseinstiege und Schutzstatus sowie bestätigte Inputs/Fillzahlen
ergänzen die Ansicht. Die Anzeige ersetzt keine Prüfung vor einem Kauf.

## Migration und Abnahme

011 nach vollständig zurückgerolltem DDL-/Runtime-/Tenantpreflight und
unabhängigem Review ausschließlich auf `investalo_credentials_checks`
angewendet. Jetzt unveränderlich:
`8065031b7eb57486013282e84b91bd6fb3c205155f9aec1ca81b5470b9430f72`.
Normale DB `investalo` bleibt001–007; Fixture001–011. Alle angewendeten
Ledgerprüfsummen verifiziert. Kein blindes Default-Migrate/Up.

170 gezielte Tests/48 Subtests im bestehenden gepinnten Pythoncheckcontainer
bestanden:37 tatsächliche PostgreSQL-/API-Fälle,12 Projektion,18 Paperworker,
54 Marktdata,45 Trading und vier Workerberechnungen. Eigener/fremder Tenant,
entzogene Mitgliedschaft, Replay, fehlender Kontext/alter Epoch und
unveränderte Writerrechte geprüft. Frische, veraltete und fehlende
Positionsquotes gesondert geprüft.

16 Cockpit-Vertrags-/tatsächliche SSR-Paneltests, Typecheck und gepinnter
Cockpitbuild bestanden. Keine neuen Dependencies und keine breite
Credential-/HTTP-Regressionswiederholung. Bestehende öffentliche Container
unverändert und gesund; Cockpit gültiges TLS/HTTP200.

```bash
python3 infra/scripts/prepare-paper-status-checks.py
bash infra/scripts/check-paper-storage.sh
cd apps/cockpit
node --experimental-strip-types --test --test-isolation=none tests/paper-status.test.ts
npm run typecheck
```

## Nächster Schritt

IP-052 bestätigt und implementiert Q32 als ausdrücklich gekennzeichnete
[H4-Schlusskurs-Modellbewertung](paper-midnight-basis.md) für die Tagesbasis00:00UTC;
Fixture inzwischen012.6%/8%, RSI-Einstiege und Quote-Ausführung unverändert.
IP-047/BL-028 bleiben offen: dauerhaft provisionierte Entwicklungsidentität,
Workerbetrieb und gesonderte Aktivierung/Abnahme der Anzeige.
[Feedvertrag](paper-market-worker.md), [offene Frage](interview.md#q32-paper-tagesbasis).

Fortsetzung IP-054: [eigene lesende Entwicklungsvorschau](paper-preview-integration.md)
aktiviert, normale DB inzwischen012. Eigener neuer simulierter Kontostand aus
begrenztem Kurslauf, getrennt von IP-053-Fixture. Die oben beschriebene
ausgeschaltete Anzeige bleibt historischer IP-051-Abnahmebeleg und Default.
