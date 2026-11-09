# Schrittweiser Crypto-Paperlauf

IP-050 verbindet diesen Kern mit [öffentlichem Feed und begrenztem Worker](paper-market-worker.md).
Tageswechsel-Dauerbetrieb und Cockpitanzeige bleiben offen.

IP-048,2026-11-09: isolierter, wiederherstellbarer Domainablauf innerhalb
IP-047. Der vorhandene `CryptoEngine` und `PaperSimulator` bleiben gemeinsam
für Forschung und Paper. Keine neue Abhängigkeit, Migration oder Aktivierung.

`PaperRunner` ist an ein vertrauenswürdig vorgegebenes Tenant/Konto gebunden.
Jedes Konto startet mit10.000 USDT; BTC/ETH teilen dessen Cash und Risk Limits.
Frische Bid/Ask-Quotes kommen vom späteren Feedadapter, geschlossene H4-Kerzen
vom Signalfeed. Es werden keine historischen OHLC-Pfade als aktuelle Kurse
oder erfundene manuelle Einstiege erzeugt.

- `bar` erzeugt Signale/Intents; es erzeugt keine sofortigen Kauffills.
- `quote` führt simulierte Orders nur für das gerade aktualisierte Asset aus.
  Käufe brauchen einen Quotezeitpunkt nach dem Signal und erneut bestandene
  Dispatchprüfung. Fees/Slippage bleiben ausgewiesene Modellannahmen.
- Identische bekannte Quotes/Kerzen sind auch nach Restore ohne Wirkung;
  Revisionen, Kursalter/Zukunft, Zeitrücklauf und Kerzenlücken werden abgewiesen.
  Gleichzeitige geänderte Quotes brauchen einen eindeutig geordneten Feed.
- Unknown Orders werden nicht erneut ausgeführt. Risk Stops bleiben gelatcht;
  manueller Puffer und Resume erhalten keine automatische Autorisierung.
- Ein Tagesbaseline wird nur mit exakten frischen Mitternachtsquotes für
  gehaltene Assets gesetzt. Fehlende Baselines blockieren neue Käufe.

## Checkpoint und Journal

Jedes Update liefert immutable Konto-/Positions-/Orderzustände, eine steigende
Revision und einen Journaleintrag mit Inputdigest, Events und bestätigten
simulierten Fills. `dump`/`restore` binden Strategie, Instrumentregeln,
Kosten, Tenant/Konto und Paper-Modus; strikt begrenztes JSON, kein Pickle.
Der Checkpoint enthält den letzten Journaleintrag, kein vollständiges Archiv.
Er ist ein vertrauenswürdiges Speicherformat, kein Authentifizierungsbeweis.

```python
from investalo_trading import PaperRunner

runner = PaperRunner(trusted_tenant_id, trusted_paper_account_id)
checkpoint = runner.start(start_utc)
update = runner.quote(checkpoint, fresh_quote, now=received_at_utc)
encoded = runner.dump(update.checkpoint)
restored = runner.restore(encoded)
```

IP-049 implementiert den [PostgreSQL-Adapter](paper-postgres-store.md):
alte Revision/Checksumme per CAS, Zustand plus append-only Journal in einer
Transaktion und ACK erst nach Commit. Unbekannten Commit durch Readback klären.
Der Disk-Roundtrip aus IP-048 bleibt ein Restoretest; laufender Feeddienst,
Feedfrische und API-Autorisierung folgen in IP-047.

## Prüfbeleg und nächste Umsetzung

84 gepinnte Tests bestanden:45 Trading (14 neue Runnerfälle),35 Marktdata,
vier Workerberechnungsfälle;48 Subtests. Restart mit bekannten Fills,
verlorenes Ergebnis vor Speicherung, assetgetrennte Ausführung, Risk-Exit,
Halts/Unknowns, Tagesbaseline, Signalalter und Snapshotbindung geprüft.
Bestehender historischer Backtestpfad verwendet unveränderte Defaults.
Aktueller Quellcode wurde schreibgeschützt in das vorhandene Checkimage
gebunden; keine Dependencies heruntergeladen oder Images neu gebaut.
Breite API-/Cockpit-/Credentialläufe aus IP-046 wurden nicht wiederholt.

IP-049 ergänzt78 gezielte Tests/15 Subtests, darunter29 echte PostgreSQL-Fälle
für CAS, atomaren Rollback, unbekannte Commits und Neustart ohne Doppelfill.
IP-047 bleibt in Umsetzung: kontrollierter Feed/Worker, Paperstatus im Cockpit
und Betriebs-/Recoveryabnahme.
Echtgeld und wirtschaftliche Holdoutvalidierung bleiben separate Gates.
