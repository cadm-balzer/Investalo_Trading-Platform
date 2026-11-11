# Futuresbuchungen aus abgeglichenen Ereignissen

2026-11-11, IP-065 innerhalb IP-063; begonnen2026-11-10.
IP-064`7007e90` in Main`ab2b6bb`
verifiziert. Neues reines Offline-Modul `futures_ledger.py`,
Version `isolated-usdt-long-ledger/1`. Bestehende Strategie-/Spot-/Paper-
Versionen, Module und Exporte bleiben unverändert.

## Kapital und Nettostand

Ein gebundener `FuturesPlan` mit3–7 Budgets bildet den Ausgangspunkt.
Der Ledger trennt unposted Cash, je Basket tatsächlich zugeordnetes eigenes
Marginkapital, **signed isolierten Nettostand**, Mark-PnL, Fees und Funding.
Fundingcredits sind Profit und erhöhen den Nettostand; sie erhöhen nicht
die ursprüngliche Kapitalzuordnung. Fundingverluste dürfen einen negativen
isolierten Stand ergeben. Fehlbeträge werden weder gekappt noch aus anderen
Positionen aufgefüllt.

Ein Kaufmargintransfer vermindert Cash und erhöht isolierten Stand/Zuordnung
um denselben Betrag; Kontoequity bleibt gleich. Entryfees gehen einmal von
Cash ab. Funding geht einmal in den isolierten Stand ein. Positive Long-
Fundingraten kosten Kapital, negative schreiben es gut. Verwendete Kosten
bleiben in der bestehenden Budgetepoche verbraucht, auch nach Zyklusabschluss;
keine automatische Erneuerung von Kostenreserven oder Gewinnkapitalfreigabe.
Wurde Funding aus der isolierten Kaufmargin bezahlt, bleibt die Deckung für
deren Wiederauffüllung reserviert. Ein ausdrücklich belegtes
`cost_restoration`-Posting stellt diesen Betrag aus dem eigenen Kostenkapital
wieder her; es erhöht weder das Kaufmarginbudget noch die schon gebuchten
Fundingkosten. Ohne tatsächliches Posting erfolgt keine Wiederauffüllung.

## Unterstützte Ereignisse

- Vollständige atomare Markbatches für alle Plansymbole.
- Explizite Tagesbasis mit exakt gleichen UTC-Mitternachtsmarks, aktueller
  Vormutations-Equity und gebundenem Evidenzdigest. Der Digest ist eine
  vertrauenswürdige Eingabe, noch kein Beweis der historischen H4-Quelle.
- Tatsächliche Teil-/Vollkäufe mit Menge, Preis, Fee, bereits gestellter
  Margin und expliziter Brokerhebeleinstellung2×–10×.
- Funding je Symbol/Zeitpunkt mit tatsächlicher signed Rate und genau
  passendem Settlementmark. Derselbe Zeitpunkt wird je Symbol einmal gebucht.
- Tatsächlich gestellte zusätzliche eigene Margin bei bestehender Position.
- Teil-/Vollschließungen mit wirklichem Ausführungspreis und Fee.

Teilkäufe senken den gewichteten Durchschnitt; der erste tatsächliche Fill
und die Zyklusidentität bleiben erhalten. Mindestordergröße wird nicht
fälschlich auf einzelne Teilfillfragmente angewandt. Mengenraster bleibt
geprüft. Eine aktualisierte Brokerhebeleinstellung betrifft die kombinierte
Position, keine automatisch ausgewählte Leiter pro Nachkauf.
Wurde die Margin bereits im ersten Teilfill vollständig gestellt, darf ein
weiteres Fragment ausdrücklich0 zusätzliche Margin buchen.

Bei Teilverkäufen wird im **expliziten Forschungsmodell** der entsprechende
Anteil des isolierten Standes und der Kapitalzuordnung freigegeben.
Preis-PnL und Exitfee gehen einmal in Cash ein. Dies ist keine belegte
historische Bitget-Marginfreigabeformel. Ein Vollabschluss liefert einen
separaten `ClosedBasket`-Record: Preis-PnL minus alle Entry-/Exitfees plus
gebuchtes Funding. Nur vollständige Zyklen erhöhen die Abschlusszahl und
realisierte Nettosumme; der Record erteilt keine Gewinnetappenberechtigung.

Beispiel, synthetisch:2 Einheiten zu100, gestellte Margin120, Entryfee0,2;
Funding−0,2, Schließung0,5 zu110/Fee0,055 und1,5 zu120/Fee0,18.
Preis-PnL35, Netto34,365. Nach vollständigem Abschluss beträgt Cash eines
10.000-Kontos10.034,365; dieselben Fees/Funding werden nicht nochmals abgezogen.

## Reihenfolge, Sperren und Herkunftsgrenzen

UTC-Uhr, Konto/Tenant/Plan und erwartete Revision binden jeden Command.
Identisches Wiederabspielen scheitert an der alten Revision. Ereignisse
mit gleichem Zeitstempel haben die versionierte konservative Forschungsfolge:
Mark → Tagesbasis → Funding → Marginposting → Einstieg → Ausstieg.
Damit bezahlt vorhandene Position vor gleichzeitigen Entries/Exits ihr
Funding. Eine spätere Marginbuchung wird nicht vor eine beobachtete Kurslücke
zurückdatiert. Nachträgliche Vormutations-Tagesbasen sind abgelehnt.

Ein Markgap erfindet weder einen Stopfill noch einen Liquidationspreis.
Menge bleibt offen, tatsächlicher Fehlbetrag bleibt sichtbar; ein später
abgeglichener Exit darf auch ein negatives Ergebnis buchen.
Aktuell gerissene6%-Tages-/8%-Originalkontolimits, unsichere isolierte Equity,
Kapital-/Kosten-/Kontraktverstöße und tatsächliche Cashdefizite bleiben
terminal gemeldet. Marginposting, Preisgewinn oder Tageswechsel heben eine
gesetzte Sperre nicht auf. Schon tatsächlich bekannte Fills nach einer Sperre
werden trotzdem wahrheitsgemäß gebucht und ausdrücklich markiert.

Nicht vollständig gedeckte künftige Budgetreserven ergeben
`reserve_shortfall`: eine Allokationssperre für künftige Käufe, kein alleiniger
Grund für einen permanenten Kontohalt. Auch kleine normale Abschlussverluste
müssen vor erneuter vollständiger Budgetvergabe berücksichtigt werden.

**Buchung ist keine Kaufgenehmigung.** Der bestehende IP-063-Kaufrechner bleibt
für−50%-First-fill-/korrelierten Kontostress vor Intent/Dispatch zuständig.
Der Ledger genehmigt keine neuen Käufe und ersetzt keine unklaren Orders,
persistenten Reservierungen, Regime-/RSI-Entscheidungen oder brokerseitige
Abgleiche. Insbesondere muss Fundingnettostand von brutto zugeordnetem
Marginkapital im späteren Riskadapter getrennt bleiben.

Hashkette bindet Command, Vorgänger und neuen State; der vollständige Journal-
speicher/CAS und globale Broker-Fill-ID-Deduplizierung bleiben offen.
Ein mit neuer Revision umetikettierter doppelter Fill wird hier allein
noch nicht als identischer Brokerfill bewiesen. Kein JSON-/HTTP-/DB-Aufrufer,
keine unbekannten Commit-/Orderwiederholungen. `execution_enabled=false`.

## Abnahme und weitere Arbeit

31 neue Fälle;218 Host-Tradingfälle und222 gepinnte Trading-/Workerfälle mit
157 Subtests bestanden. Ökonomische Prüfung von Cash/Equity, Teilfills,
signed Funding, vollständigem Nettoabschluss, sieben Slots, Revisionen,
Zeitsprüngen, Fehlbeträgen und dauerhaftem Halt. Deklarierter echter Fill
stimmt für3/5/7 Slots exakt mit der bisherigen Kaufprojektion überein.
Decimalarithmetik ist vom globalen Kontext isoliert.
Fachliche Eigenprüfung trennt Reserveshortfall von Kontohalt und verhindert
doppelte Fundingbuchung trotz neuem Eventnamen/neuer Revision.

Weitere tatsächliche Fundingarchive bleiben offen. Die aktuelle
[V3-Dokumentation](https://www.bitget.com/docs/catalog/market/derivatives)
beschränkt Fundinghistorie auf90 Tage, paginiert statt Zeitfenster.
Der [öffentliche Downloadbereich](https://www.bitgetapp.com/docs/uta/data-download-center)
nennt für Marktdaten Kerzen/Trades/Depth; persönliche Fundingabrechnungen
sind kein belegtes vollständiges öffentliches Marktarchiv. Keine Abfragen
des reservierten Holdouts oder Ersatz durch Null/heutige Raten.

Für Brokerhebel2× bleibt der effektive Anfangshebel mit bereits gestelltem
eigenem Puffer unter2× möglich. **Der Brokeradapter muss nachweisen, dass
dieser Puffer rechtzeitig wirksam ist.** Zwei zeitlich getrennte Aufrufe sind
keine automatisch atomare Deckung eines unmittelbaren Gaps nach erstem Fill.
Fehlender Nachweis blockiert die spätere entsprechende Ausführung.
2× ist die bestätigte Untergrenze unseres Forschungsprofils; aktuelle
Kontraktmetadaten und effektiver Hebel sind davon getrennte Größen.

IP-066 verbindet als Nächstes Kaufprüfung, pending Intents/Teilfills,
Abgleich und Buchungszustand mit expliziten tatsächlichen Margin-/Costgrößen.
Historische Funding-/Fee-/Maintenanceannahmen, exakte Regime-/Budgetregeln
und echte Futuresnettoläufe bleiben IP-055/063/BL-030.
Keine neuen Dependencies, Migrationen, Runtime-/Broker-/Publicänderungen.
