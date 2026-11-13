# Native H1-RSI-Einstiege im Futures-Kapitalprofil

IP-080 vergleicht zunächst ausschließlich H1- gegen H4-RSI-Einstiege.
Beide verwenden 10000 USDT, fünf feste Slots, dieselbe volle eigene
Sechsstufenstaffel, isolierte 2×-Long-Baskets und H1-Supertrend-Schutz.
Die sechste Stufe bleibt ausschließlich manuell; sie wird nicht simuliert.
Profitreinvestition bleibt in diesem isolierten Vergleich aus.

Vor der ersten H1-Leistungsauswertung eingefroren:
`research-protocols/futures-capital-h1-entry-20261112.json`,
SHA256 `23aefed3d96ff6cb9eb6b404209fc67f227529904131463941ec0c2fb7cb39f1`.
Referenz ist der vollständig restaurierte korrigierte `base-h1-2x`-Fall
mit H4-Einstiegen: netto +2507,71 USDT, maximaler Ereignisdrawdown 9,86 %,
107 Abschlüsse und eine Liquidation. Das gebundene Referenzreceipt
`futures-capital-cash-market-receipt-20261112.json` hat SHA256
`979880a5b9fdcadc1a8aa8f11f23e7e1af158c86b68d4ea3d27c2b282470476e`.

Das neue `CapitalH1SignalProfile` verwendet RSI14/Wilder aus ausschließlich
geschlossenen nativen H1-Trade-Kerzen. Zwei aufeinanderfolgende Werte strikt
unter 30 bestätigen den ersten Kauf. Nach jedem tatsächlichen Fill muss RSI
zuerst strikt über 30 und anschließend wieder unter 30 schließen. Zusätzlich
muss der maximale tatsächliche Fillpreis höchstens 95 % des letzten
tatsächlichen Kaufpreises betragen. Schutzmodus sperrt weitere Käufe.
Warmup, frische Schlusszeit und aktuelle Margin-/Liquidationsprüfungen gelten
weiter. H1-Erholung und Nachkauf werden nicht aus einem H4-Schluss abgeleitet.

Signalpolicy `isolated-usdt-capital-signals-h1/2` und Journal
`isolated-usdt-capital-replay-journal-h1/2` erhalten eigene Identitäten.
Der Restore dekodiert die fest bekannte Policy, prüft die Genesis und faltet
sämtliche Befehle. H4-Profilfelder, bisherige Hashdomänen und bestehende
Journalidentitäten bleiben unverändert. Ein H1-Journal kann nicht als
H4-Profil oder umgekehrt restauriert werden.

Expliziter create-only Offlinejob:

```sh
python3 infra/scripts/backtest-futures-capital.py --h1-entries NEW_OUTPUT_DIRECTORY
```

Er prüft die Protokoll- und Referenzhashes, verwendet dieselben fünf nativen
BNB/BTC/ETH/SOL/XRP-Quellen vom 2022-08-01 bis 2025-08-01 exklusiv
und führt nur den vorab erklärten 2×-Basisfall aus. Next-Open+2s-Fills,
Gebühren, Fundingoffsets, Markbewertungen, Margin, Gapexits und
−55%-Notausstieg entsprechen dem H4-Einstiegsvergleich. Keine M15-Kerzen
oder Tickfolge werden erfunden. Derselbe H1-Trailing isoliert die Wirkung
des Einstiegstimeframes.

Zu berichten sind Netto, Drawdown, Liquidationen, alle tatsächlichen
Kaufstufen, Kapitalnutzung, Signal-/Finanzierungsablehnungen und ein
vollständiger Journalrestore. Mehr Signale sind kein zugesicherter Gewinn.
Historische Brokerregeln und Kostenkalibrierung bleiben offene Modellgrenzen;
Holdout, KI, Cockpit-/Paperprofilwechsel und Liveausführung sind nicht aktiviert.
