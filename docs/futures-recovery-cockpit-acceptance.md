# Lokale Cockpitabnahme der manuellen Wiederbelebung

Q46/IP-088 verbindet hier die vorhandene Startseiten-/Portfolioanzeige mit
dem tatsächlichen HTTPS/BFF/API/PostgreSQL/Journalpfad. Ein eigenes
synthetisches Fixturekonto nutzt sieben Kandidaten, drei vollständig
finanzierte Ranges und feste2×. Deklarierte Preise/Contractregeln erzeugen
über die normalen Reducer drei profitable Vollschließungen, neue Baskets
und eine tatsächlich im Paperjournal gebuchte Modellliquidation.
Das ist keine neue Marktperformance oder native Brokerliquidation.

Die getrennten Compose-Dienste besitzen keine Hostports. Nur die geschützte
Fixture-DB mit bestehender013 und die eigenen0700/0600-Verzeichnisse werden
benutzt. Originalallocation und Journalpfad sind für API und Launcher an
dieselbe private absolute Mountstelle gebunden. OIDC-Identität/verschlüsselte
Session sind synthetisch; TLS, BFF-Signatur, scoped API, restricted LOGIN/RLS,
aktuelle Einstellungen, Recoveryexecutor und Filesystemlocks sind tatsächlich.
Browserklick/Hydration/MFA werden mit dieser HTTP-/SSR-Abnahme nicht behauptet.

Geprüft werden sichtbarer Startseitenblocker, Assetdetails mit Verlust/
benötigtem Neubudget, initiale Zustimmung und deaktivierter Button sowie
Ablehnung fehlender Anmeldung, falscher Origin/CSRF, fehlender Zustimmung
und fremder Actor-/Cashbehauptungen. Nach echter31s-Zeitüberschreitung bleibt
die Freigabe gesperrt und das Journal unverändert.

Der begrenzte Launcher läuft anschließend zwei Zyklen. Ausschließlich die
Quelle und das Zwischenzykluswarteobjekt sind injiziert: Die synthetischen
Beobachtungen besitzen kein natives Quellenarchiv. Journal, eigene
Accountreads, Registry, Launcherlocks und manuelle HTTPS-Aktion bleiben real.
Während der Writer gehalten wird liefert die Aktion503; veraltete Revisionen
liefern409. Erst im freien Zwischenzyklus bestätigt eine neue ausdrückliche
Aktion die Freigabe. Ein vollständiger Restore beweist dieselben Cash-/Netto-/
Tagesbasen, Peerpositionen und Kaufhistorien. Nur der Zielstop, die neue
RSIbestätigung und das zukünftige Zielkostenbudget werden zurückgesetzt.
Der zweite Zyklus übernimmt den tatsächlich publizierten APIreceipt.
Beide SSR-Seiten entfernen anschließend den Liquidationsblocker.

Die Vorabablehnung alter Publikationsrevisionen/Quotes erspart sinnloses
Vollreplay. Aktuelle Anfragen benötigen weiter den vollständigen gesperrten
Journalabgleich und aktuelle Actor-/Budgetprüfung. Die manuelle BFF-Aktion
besitzt8s innerhalb der10s-Clientfrist; sonstige Abrufe bleiben bei5s.
Unbestätigte oder abgebrochene Aktionen erhalten keinen automatischen Retry.
Große Journale und unbegrenzter Dauerbetrieb benötigen gesonderte
Latenz-/Betriebsabnahme; diese kurze Fixture belegt das nicht.

## Lokale Wiederholung

Zuerst ausschließlich die vorbereiteten Testverzeichnisse herstellen:

```bash
python3 infra/scripts/prepare-passkey-browser-checks.py
python3 infra/scripts/prepare-futures-local-acceptance.py --recovery
```

Compose verbindet `infra/compose.yaml`,
`infra/compose.passkey-browser-checks.yaml` und
`infra/compose.futures-recovery-acceptance.yaml`, Projekt `investalo-local`,
gepinntes `infra/images.env`. Nur `browser-proof-api`,
`browser-proof-cockpit` und `browser-proof-edge` starten; anschließend
`--profile futures-recovery-checks run --rm --no-deps -T futures-recovery-checks`.
Start vor Minute57 und nach den ersten fünf Sekunden einer neuen Stunde.
Danach ausschließlich die drei Fixturedienste stoppen; kein `down` oder
`--remove-orphans`. Normale/public Dienste werden nicht ersetzt.

Der Driver legt jeden Lauf create-only unter
`/tmp/investalo-futures-recovery-acceptance/<uuid>` an. Ausschließlich ein
vollständig erfolgreicher Lauf besitzt `acceptance-receipt.json`.
Er enthält Originaljournalanker, volle Restorebestätigung und ausdrückliche
Kennzeichnungen für synthetische Quelle/Identität, fehlende physische
Browserabnahme und deaktivierte Ausführung/Public/AI.

## Ergebnis vom 2026-11-15

42 tatsächliche HTTPS/PG/SSR-Prüfungen bestanden. Lauf
`bcfb57cf176e4091880a7d76c2e289af`, Receipt-SHA256:
`24466bf194edb5b9758101316db63d9df1961d1e0fa2736bbf9c6456b1b2491c`.
Workerrevision11, manuelle Freigabe12, vollständig restaurierter Folgezyklus13;
die zwei injizierten Quotezyklen selbst erzeugten keine Einstiege/Schließungen.
Die drei Fixturedienste wurden danach gestoppt.

Originalallocation, synthetisches Journal, initialer eigener Recoveryabruf,
Receipt, vier abschließende Test-/Buildlogs und Dateihashes sind byteidentisch
und create-only persistent unter
`infra/local/futures-recovery-cockpit/20261115-local` gesichert.
Die vor dem Serverneustart fehlgeschlagenen temporären Läufe existieren nach
dessen `/tmp`-Bereinigung nicht mehr; sie besitzen keinen Erfolgsnachweis.

Vor dem Neustart82 betroffene gepinnte Pythonfälle/25 Subtests grün.
Nach dem Neustart final21 Recoveryfälle/7 Subtests einschließlich zusätzlicher
Vorabablehnung erneut grün;575 Cockpitfälle und Typecheck erneut bestanden.
Gepinntes Cockpitimage gebaut, neue Module im gebauten normalen APIimage
ohne Netzwerk/Quellcode-Testmount geprüft. Keine Schema-/Dependencyänderung,
kein Marktjob und keine öffentliche/Broker-/AI-Aktivierung.

Siehe [Recoveryvertrag](futures-manual-recovery.md) für die unveränderte
vollständige Neubudget-/Verlust-/Reserveprüfung und separate Demoanbindung.
