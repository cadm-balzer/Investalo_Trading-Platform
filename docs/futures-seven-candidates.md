# Sieben native Classic-Futures-Kandidaten

IP-090, 2026-11-14. PR69 (`06564fa`) ist in `main9210f70` enthalten;
GH/Fetch/Ancestry bestätigt.

Das ausdrücklich neue Profil umfasst AVAX, BNB, BTC, ETH, LINK, SOL und XRP,
jeweils USDT-M auf Bitget Classic. LINK und AVAX stammen aus der bestätigten
Kandidatenauswahl. Kanonische Symbolreihenfolge ist alphabetisch wie im Ledger.
Diese Auswahl erweitert den tatsächlichen Quellenumfang, nicht das Kapital:
10.000 USDT, drei anfänglich finanzierte vollständige Ranges, Obergrenze sieben,
feste2×, H1-RSI/H1-Supertrend und die bisherigen sechs Eigenkapitalstufen.
Weitere Plätze brauchen weiterhin die bestätigten [Gewinnetappen](futures-paper-profit-epochs.md).

`local_seven_profit_config` bindet alle sieben eigenen aktuellen Vertragsraster
und einen separaten Ökonomiedigest `/3`. Gebühren, Maintenance, Geldquantum,
Slippage und Fills bleiben erklärte Paperannahmen; keine Brokerorderfreigabe.
Private Allokation/Genesis sind erforderlich. Vorhandene feste oder Fünf-Coin-
Gewinnjournale werden nicht konvertiert, zurückgesetzt oder doppelt finanziert.
Die normalen Launcher wählen die Quellenkohorte aus dem vertrauenswürdig
geladenen eigenen Genesisprofil; ein UI-Limit allein erweitert keinen Pool.

## Quellen, Funding und Restore

Der explizite Sieben-Coin-Collector sammelt35 unsigned GETs: separate geschlossene
H1-Trade-/Markachsen, native Fundinghistorie und Forecast je Coin, danach eigene
frische Quotes. Fremde/fehlende/umgeordnete Kandidaten und Lücken werden abgelehnt.
25s-Kohortenfrist und30s-Frische bleiben gleich. Zusätzliche Daten werden nicht
von einem anderen Asset übernommen. Die fünf bisherigen Defaultkandidaten,
deren `/1`-Records, Archive und Forschungsidentitäten bleiben erhalten.

Neue Quellenrecords und Settlement-Evidence tragen `/2`. Das bestehende private
Archiv prüft35 statt25 bzw.14 statt10 Antworten, gebunden an die tatsächlich
dekodierte Kohorte. Originale kanonische Responses werden vollständig offline
wieder geparst. Keine Netzwerkabhängigkeit beim Restore.

Funding verwendet weiterhin native IDs/Raten und die bestätigte Q49-Minuten-
Open-Referenz. Sieben Fundingraten und sieben zugehörige Mark-Minuten werden
gemeinsam archiviert; sie sind keine exakten Broker-Settlementmarks.
Unterschiedliche künftige Fundingtermine werden nicht durch Ersatzraten,
weggelassene Coins oder verschobene Zeiten repariert. Fehlt die vollständige
benötigte Kohorte, greift der vorhandene Reconciliationstop.

Aktuelle Contractsberatung, normale scoped Assets-/Kapazitäts-API und bestehender
Cockpitvertrag unterstützen dieselben sieben eigenen Symbole. Sieben geeignete
Assets bei drei finanzierten Ranges ergeben weiterhin Empfehlung drei.

## Prüfbelege

Sieben neue Fälle: sechs Domain-/Quellen-/Archiv-/Workerfälle und ein tatsächlicher
PG-/HTTP-Fall. Das neue native Profil durchläuft synthetisch3→4→5→6→7,
schließt danach tatsächlich sieben Baskets und erhöht erst anschließend das
Budget zukünftiger Ranges. Vollständige Fundingabrechnung mit sieben IDs,
14-Response-Replay, Journalneustart ohne Doppelabrechnung, fehlende Daten,
Metadaten/Poolidentität, privater Allokationsrundlauf und fremde HTTPkonten geprüft.
Große synthetische Gewinne belegen Schwellen, keine Marktperformance.

178 gepinnte Regressionsfälle/130 Subtests grün; danach43 gezielte Fälle/
42 Subtests und alle sieben neuen Fälle final erneut grün (sieben Subtests).
Keine Frontendänderung oder neuer Build erforderlich.

Tatsächliche native Abnahme:
`infra/local/futures-seven-acceptance/20261114-native-1`.
Zwei35-GET-Marktarchive und ein14-GET-Funding-/Minutenarchiv; zwei zusätzliche
Contracts-GETs für Profil und aktuelle Beratung. Warmup22 geschlossene Stunden
pro Achse, gemeinsame native Fundingminute2026-11-14T16:00Z.
Aktuelle Mengenraster AVAX.1/BNB.01/BTC.0001/ETH.01/LINK1/SOL.1/XRP1;
alle sieben aktuell `normal` und2× möglich. Vollständiger nativer Archiv-/
Journalrestore und gemeinsame Statuspublikation bestätigt: Journalrevision2,
sieben Assets/sieben geeignete Kandidaten/drei finanzierte Plätze.
Keine Entries/Closures im kurzen Lauf und keine Performanceaussage.
Receiptsha:
`afdbd364c1707176efd27b2a4dc3a9b59152c6915a379a0da42eea62d91e3c68`.

Reproduzierbarer eigener Befehl unter einem vorhandenen owned0700-Elternordner:

```sh
python3 infra/scripts/check-futures-seven-candidates.py NEUER_PRIVATER_ORDNER
```

Er verwendet ausschließlich ein neues synthetisches Paperkonto, öffentliche
GETs und private lokale Dateien. Keine bestehenden Konten, DBmigrationen,
laufenden Dienste oder Brokerorders. Receipt erst nach vollständigem Restore;
fehlgeschlagene Verzeichnisse bleiben ohne Erfolgsreceipt erhalten.
Der erste Elternpfad wurde vor Erstellung wegen fehlendem0700 abgelehnt;
daraufhin wurde ein eigener privater Abnahmeroot verwendet.
`capture-futures-paper-feed.py --seven-candidates` bietet außerdem reine
35-GET-Quellenaufnahme ohne Worker.

Nächster Schritt: Q46/IP-088 manuelle Liquidationsfreigabe in eigene dauerhafte
Paperpersistenz/API/Dashboard integrieren; anschließend getrennte Bitget-Demo-
Orderkalibrierung. Keine Public-/Live-/AI-Aktivierung.
