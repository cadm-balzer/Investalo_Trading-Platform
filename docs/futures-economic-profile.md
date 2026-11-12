# Eingefrorenes Wirtschaftsprofil für den Futures-Nettovergleich

IP-077,2026-11-12. IP-076`29d76d9` ist in Main verifiziert. Die native
Fünf-Coin-H1-Quelle und der vollständige Kapitaljournalrestore sind vorhanden;
dieser Checkpoint friert die wirtschaftlichen Annahmen vor Leistungsauswertung
ein und ergänzt exakte gleichzeitige Fundingverarbeitung.
**Noch kein neuer Nettoleistungslauf.** Der vollständige Marktjob folgt in IP-074/IP-069.

[Protokoll](research-protocols/futures-capital-economics-20261112.json),
SHA256`eb9a278513facb4f7560413c6ae269dc2fd44adf917eec00ebec9925ddcc8c06`.
BNB/BTC/ETH/SOL/XRP,2022-08-01..2025-08-01. Fünf feste Symbolslots,
10000 USDT, bisherige sechsteilige Eigenkapitalstaffel und1%-Kostenreserve.
Normale Abschlüsse erlauben denselben Slot erneut, Liquidationen bleiben
terminal. Stufe6 wird nicht automatisiert; Gewinnetappen/Slotwachstum werden
im ersten Vergleich nicht eingerechnet. Kein AI-Modell oder Holdoutzugriff.

## Annahmen und zehn vollständige Vergleichsfälle

| Größe | Basis | Kostenstress |
|---|---:|---:|
| Entry-/normale Exitfee | je0,1% | je0,2% |
| Adverse Slippage je Ausführung | 0,05% | 0,1% |
| Ganze-Nominal-Maintenance | 0,5% | 1% |
| Modell-Liquidationsfee | 0,5% | 1% |
| Positives Funding | native Rate | doppelte native Rate |
| Negatives Funding | native Gutschrift | unveränderte native Gutschrift |

Diese Werte sind erklärte Forschungsannahmen, keine historischen Binance-
oder Bitgettarife. Einheitliches Mengenraster0,00000001, Mindestnominal5 USDT,
Maintenance-Cap1000000 USDT und maximal10× sind ebenfalls Modellannahmen.
Das Cap ist exklusiv; jenseits fehlt Deckung statt stiller Standardstufe.
Die1%-Kostenreserve garantiert keine vollständige Kostendeckung.
Echte Budget-, Initialmargin- und Liquidationsconstraints bleiben erhalten;
6%/8% und gemeinsamer−50%-Stress sind Warnungen/Diagnose nach Q41–Q43.

Sechs Basisfälle:2×/5×/10× jeweils mit H1- oder H4-Schutz und H4-RSI-Einstiegen.
Zwei Kostenstressfälle bei2×, ebenfalls beide Schutzintervalle.
Zwei weitere2×-Fälle ändern ausschließlich die deklarierte Intrabarreihenfolge.
Alle zehn Fälle werden berichtet; keine nachträgliche Wahl des günstigsten Pfads.

Basisweg: Open→Low→High→Close; alternative Reihenfolge Open→High→Low→Close.
Openmodell bei+1s, Extrema bei+20/+40min, native geschlossene Stunde exakt
am folgenden Stundenbeginn. Diese Zeiten/Pfade sind ausdrücklich simuliert,
keine beobachteten Tickfolgen. Beide Schutzvarianten verwenden dieselben
Quellen und denselben erklärten Weg. Erst geschlossener H4-RSI erlaubt Käufe;
kein weiterer H1-Einstieg. Vollfillmodell ohne Brokerorder-/Teilfillautorität.
Endbestände werden mark-to-market bewertet; keine erfundenen Profitabschlüsse.

## Native Fundingzeiten und fehlende Settlement-Marks

`funding_reference` erhält originale Millisekundenzeiten und signed Rates.
Vorhandene Settlement-Marks bleiben erhalten;6920 fehlende Marks werden
ausdrücklich mit dem Open der enthaltenden nativen H1-Markkerze angenähert.
High/Low/Close dieser noch offenen Stunde beeinflussen den Nominalpreis nicht.
Vollständige Kerzen-/Datasetdigests binden die Quellenprovenienz; das ist
keine Behauptung, den späteren Kerzenverlauf als damaliges Signal zu kennen.
Unterstützt werden0..999ms nach voller Stunde; andere native Zeiten stoppen
die Vorbereitung, ohne sie zu verschieben. Zero ist eine vorhandene Rate.

Die nativen Kerzen behalten`BINANCE:<symbol>:USDT-M:<kind>`.
Der Plan verwendet daher`BINANCE:<symbol>`; diese Quellenidentität wird nicht
gestrippt oder mit Bitget vermischt. Native Header-Ticker bleiben unverändert.

10937 Abrechnungen liegen exakt auf voller Stunde. Die neue explizite
`valued_hour`-Transition setzt die vollständige Funding-Markbewertung vor der
UTC-Tagesbasis, ohne die geschlossenen Trade-/Markkerzen oder RSIinputs zu ändern.
Gewöhnliche`hour`-Transitionen bleiben identisch. Revisierte valued Hours
werden verweigert; kein stiller erneuter Preiswechsel.

`CapitalFundingBatch` fasst alle gleichzeitigen Settlements kanonisch
zusammen. Vollständige exakte Markbewertung muss bereits vorliegen.
Zwischen diesen Buchungen gibt es keinen Kauf/Exit/Marginwechsel. Jede
Settlement-ID bleibt einzeln erhalten; ein fehlerhaftes späteres Settlement
übernimmt auch kein erstes Settlement und schreibt keinen halben Journalrecord.
Beide neuen Commands werden aus dem Journal vollständig restauriert.

## Ausstiege und explizite Liquidationsannahme

Normale Exits verwenden den beobachteten Modell-Tradepreis minus Slippage;
ein Gap kann unter dem Nettofloor schließen und einen realisierten Verlust
ergeben. Das Profil garantiert keine Fillpreise am Stop.

Liquidationsmodell: aktueller unsicherer Markzustand, kleinerer Wert aus
aktueller Trade-/Markreferenz minus Slippage, gesamte verbleibende Menge,
Liquidationsfee und abgeglichener zurückgegebener Marginstand.
Negatives Terminalsaldo wird durch eine **explizit angenommene isolierte
Versicherungsgutschrift** ausgeglichen. Diese Gutschrift wird separat belegt,
nicht als Gewinnstrategie oder tatsächliche historische Brokerleistung.
Ohne diesen historischen Beleg ist das Ergebnis ein erklärter Modellvergleich.

Keine neue Preisbeobachtung vor terminalem Abgleich. Eine spätere Erholung
ersetzt das ursprüngliche unsichere Preisbild nicht. Falls bereits fälliges
Funding bei unverändertem Preis rechnerisch heilt, benötigt die spätere
Modellabrechnung den unveränderten ursprünglichen unsicheren Zustand als
zusätzlichen vertrauenswürdigen Eingang; dessen Digest ist im Beleg gebunden.
Das ist kein kryptografischer Nachweis einer Brokerliquidation.
Kostenrestoration nur aus eigener Costreserve und nach Liquidationsprüfung;
keine Rettungsüberweisung aus reservierten Kaufstufen oder fremden Baskets.

## Tatsächlicher Quellen-/Profilpreflight

`python3 infra/scripts/preflight-futures-capital.py NEW_OUTPUT_DIRECTORY`
liest ausschließlich die gespeicherten Quellen. Protokoll-/Quellenreceipthashes
werden vorab fest geprüft; fünfzehn Quellenfiles, Datasetdigests, vollständige
Fenster und Trade-/Markachsen erneut abgeglichen. Keine neuen Netzwerkdaten.
Fundingdigest einmal pro Stream, nicht für jede Referenz neu über alle Zeilen.
Create-only Ausgabeverzeichnis und Erfolgsreceipt erst nach vollständigem Lauf.

[Abnahmereceipt](research-protocols/futures-capital-preflight-receipt-20261112.json):
263040 Preiszeilen,16515 Fundingevents,3363 native Zeitgruppen, maximal fünf
gleichzeitige Settlements. Je Profil9595 native Marks/6920 Open-Näherungen;
Kostenstress verdoppelt11335 positive Raten, negative bleiben unverändert.
Alle zehn Profile/Assumptiondigests und Quellenhashes sind gebunden.
Rohdaten und vollständiges lokales Receipt bleiben in
`infra/local/futures-capital-research/20261112-preflight-complete/`.

Erster Preflight ohne Receipt am Identitätsfehler abgebrochen. Ein weiterer
eigener Lauf nach Identitätskorrektur wurde wegen unnötiger Digest-Neuberechnung
gezielt beendet. Keine Erfolgsausgabe/Artefaktüberschreibung; neuer eigener
Output nach Korrektur vollständig abgeschlossen. Gebühren/Pfade wurden dabei
nicht anhand von Marktperformance geändert; es wurde keine Performance berechnet.

Gezielte Prüfung umfasst Modellparameter/Protokollbindung, Fundingpreis-/Zeit-
provenienz, native Identität, Kostenstress, Gapverlust, explizite Versicherung,
Recovery-Verweigerung, echte Mitternachtsinventarbewertung, atomare Batches
und vollständigen Restore. Alte Signal-/nahe Journalverträge bleiben geprüft.
Keine Dependencies, Migrationen, DB-/Runtime-/Paper-/Publicaktivierung.

27 neue/56 unterschiedliche gezielte gepinnte Fälle bestanden: zuerst53 Fälle/
26 Subtests, nach nativer Identitätskorrektur16 Profilfälle, anschließend
drei neue Preflightfälle plus finale Identitätssubprüfung sowie drei betroffene
Liquidationsevidenzfälle. Überlappungen nicht addiert. Eigenreview; keine
Delegation oder breiten DB-/Credential-/UI-Wiederholungen.
