# Lokale Futures-Paperabnahme

IP-090, 2026-11-14. PR66 (`218f36f`) ist in `main7ce1be4` enthalten;
GH-Status, Fetch und Ancestry sind bestätigt.

Der eigene gebundene CLI-Worker wird erstmals mit aktuellen nativen Bitgetdaten
bis durch die tatsächlich laufende private HTTPS-/Next-/API-/PostgreSQL-Kette
geprüft. Die öffentliche Entwicklungsvorschau wird dabei nicht umgeschaltet.
Es gibt keine Echtgeldorders, Brokerkeys oder neuen Abhängigkeiten.

## Konkretes lokales Modell

`futures_local_profile.py` bindet den SHA der fünf originalen aktuellen
Classic-Vertragsobjekte. Normaler Instrumentstatus, vollständige geordnete
BNB/BTC/ETH/SOL/XRP-Kohorte und erlaubte2× sind erforderlich.
Mengenraster, Mindestmenge, Mindestnotional, Preisraster und maximale
Marktmenge kommen aus dieser Quelle und bleiben für diesen Lauf eingefroren.
Eine laufende private Instrument-/Brokerkalibrierung ist damit nicht belegt.

Explizite Paperallokation:10.000 USDT, drei anfänglich vollständig finanzierte
Ranges und fünf Kandidaten, gespeicherte Obergrenze standardmäßig5.
H1-RSI14, fünf reguläre Käufe plus ausschließlich manuelle sechste Reserve,
H1-Schutz, fester2×-Baskethebel und Q49-Fundingbewertung bleiben erhalten.
Eine Obergrenze5 erzeugt weiterhin nur drei finanzierte Plätze.

Modellannahmen sind separat erklärt und in die Configidentität eingebunden:
1% Kostenreserve, USDT-Quantum0,00000001, Entry-/Exitfee jeweils0,06%,
Slippage0,05%, ein erklärter Maintenance-Tier0,5% bis1 Mio. Notional,
Liquidationsfee0,1% und angenommener Insurancecredit.
Öffentliche Tarife werden nicht als eigene Kontogebühren übernommen.
Maintenance, Geldrundung, Insurance und vollständige Paperfills sind
Modellannahmen; keine bestätigte Brokerzulassung oder neue Profitstudie.

## Isolierter Prüfweg

`prepare-futures-local-acceptance.py` erstellt ausschließlich den markierten
privaten Mount `/tmp/investalo-futures-local-acceptance`, owned10003:10010/
0700, mit eigenem Statusunterverzeichnis. Bestehende Artefakte bleiben erhalten.
Der bestehende synthetische Browserprüfmount wird separat verifiziert.
Das neue Composeoverlay ergänzt nur die bestehenden Browserprüfdienste;
keine Hostports, keine Änderungen der normalen API/Cockpitservices.
Die API sieht ausschließlich den readonly Statusmount.

`check_futures_local_cockpit.py` legt eine neue synthetische eigene
Owner-/USDT-Paperidentität ausschließlich in `investalo_credentials_checks`
an.013 muss dort bereits existieren; keine Migration, Rolle oder Grant wird
erzeugt. Die verschlüsselte synthetische Sitzung entsteht ausschließlich
im bestehenden geschützten Fixturemount mit dessen eigenen Prüfsecrets.
Das bestätigt keine physische Browser-/MFA-Anmeldung eines echten Nutzers.

Der vollständige Ablauf prüft:

- Einmalige SHA-gebundene private Allokation, native Mitternachtswarmupdaten,
  aktuelle Quotes und erste bestätigte Publikation.
- Authentifizierten echten HTTPS-APIabruf, eigene Kontosicht und fünf native
  H1-RSIwerte. Der direkte Prüfabruf verbindet zum eindeutigen Testservice,
  prüft weiterhin die TLS-Zertifikatsidentität `api`; der normale Dienstname
  ist im ebenfalls verbundenen Datenbanknetz mehrdeutig.
- Tatsächliches Next-SSR auf Übersicht und Portfolio über HTTPS/BFF/API;
  der strikte TS-Vertrag akzeptiert die echten Werte und rendert die Tabelle.
- Unauthentifizierten BFF-Schreibschutz sowie tatsächlichen CSRF-/CAS-Write
  der Obergrenze5→3 mit genau einem eigenen atomaren Audit.
- Neues CLI-Programm mit Minimumreceipt-Vollrestore, Quellenfortsetzung,
  angewandter013-Revision1 und unveränderten vollständig finanzierten Budgets.
- Nach31 Sekunden ohne Worker bleiben Quotezeit/RSI erhalten, Kaufbedingungen
  bekommen `data_stale`; das tatsächliche SSR zeigt den Datenstandsblocker.
- Eine nachträgliche eigene Kontopause stoppt den nächsten CLI-Aufruf vor
  weiteren Quellenkohorten und Journaländerungen; die API zeigt die Pause.

Jeder Lauf erhält ein neues0700-Verzeichnis. Allokation, native Originalquellen,
Journal, öffentliche Modellerklärung und drei gelesene Assetsnapshots bleiben
erhalten. Erst nach allen Prüfungen entsteht ein create-only/fsync/readback
Acceptance-Receipt. Fehlgeschlagene Verzeichnisse bekommen kein Erfolgsreceipt.
Synthetische Konten bleiben für die nachvollziehbare Abnahme erhalten.

## Tatsächliches Ergebnis

Drei neue gezielte Profilfälle und44 fokussierte gepinnte Fälle/15 Subtests
sind grün. Der gepinnte Cockpitbuild ist grün; die tatsächliche HTTP-Kette
akzeptiert den vorhandenen TS-Vertrag ohne UIänderung.

Der vollständige native Lauf hat43 Prüfungen bestanden:
`/tmp/investalo-futures-local-acceptance/b3a5130e572347009bce18e73d174acc`.
Das create-only Abnahmereceipt hat SHA
`1c5c65b52bce453ab2d767baa23a62d995f420e02889c1a71996695030f2525a`.
Journalrevision2 nach erstem Quotestand, Revision4 nach gespeichertem Limit
und echtem CLI-Neustart. Kein Entry/Exit in diesem kurzen Prüfzeitraum;
keine zukünftigen oder nachträglich erzeugten Fills.
Aktuelle RSI-/Frischeanzeige, unveränderte Kaufbudgets, tatsächliches
Settingsaudit und Pause vor weiteren HTTP-/Journalaktionen sind bestätigt.

Der erste native Lauf blieb nach erfolgreicher Workerpublikation an der
mehrdeutigen APIadresse ohne Abnahmereceipt stehen. Sein Verzeichnis und
seine Quellen wurden erhalten; zwei reine HTTP-/SSR-Diagnosen änderten
sein Journal nicht. Der abschließende Lauf nutzte eine neue Allokation und
einen neuen Actor, ohne Reset oder Überschreiben des alten Paperkontos.
Die isolierten Prüfdienste werden nach der Abnahme wieder gestoppt.

## Lokaler Aufruf

Nur nach vorhandener Fixture013 und vorbereiteten lokalen TLS-/DB-/Browsersecrets:

```bash
python3 infra/scripts/prepare-passkey-browser-checks.py
python3 infra/scripts/prepare-futures-local-acceptance.py
bash infra/scripts/compose.sh build cockpit
bash infra/scripts/compose.sh \
  -f infra/compose.passkey-browser-checks.yaml \
  -f infra/compose.futures-local-acceptance.yaml \
  --profile passkey-browser-checks up -d --no-deps --wait \
  browser-proof-api browser-proof-cockpit browser-proof-edge
bash infra/scripts/compose.sh \
  -f infra/compose.passkey-browser-checks.yaml \
  -f infra/compose.futures-local-acceptance.yaml \
  --profile futures-local-checks run --rm --no-deps -T futures-local-checks
```

Der Lauf beginnt spätestens vor Minute57, damit kurze HTTP-/Neustartprüfungen
nicht über eine neue H1-Grenze laufen. Er ist ausdrücklich begrenzt; keine
dauerhafte Workeraktivierung, kein Broker-Demodienst, keine öffentliche Freigabe.
Die interne Planungs-API bleibt bis zur kalibrierten Kapazitätsanbindung
`runtime_ready=false`/`recommendation=null`, auch wenn die Assetanzeige arbeitet.
Danach folgen Kapazitätsreader, Q36-Gewinnetappen, IP-088-Recovery und Bitget-Demo.

## Fortsetzung nach PR67

Der oben dokumentierte 43-Punkt-Beleg bleibt historisch unverändert.
Die [Paperkapitalempfehlung](futures-paper-capacity.md) ergänzt inzwischen den
kalibrierten Reader und hat eine eigene native 60-Punkt-Abnahme bestanden.
Im dort ausdrücklich aktivierten lokalen Overlay ist die Planungs-API bei
frischen bestätigten Daten nun bereit; drei finanzierte Ranges empfehlen drei.
Q36-Gewinnetappen und IP-088-Recovery bleiben die nächsten Schritte.
