# Futures-Kaufprüfung und begrenzter Orderabgleich

2026-11-11, IP-066. IP-065`12c2b6c` in Main`ffd4211` verifiziert.
Neues separates Offline-Modul `futures_pending.py`,
Version `isolated-usdt-long-pending/1`. Bestehende Spot-/Paper-,
Futures-Risk-v1- und Ledger-v1-Versionen bleiben unverändert.

## Kaufprüfung am Buchungsstand

`assess_ledger_purchase` verwendet das ursprüngliche gebundene Konto mit
3–7 Slots und die tatsächlich gebuchten Größen:

- Brutto zugeordnetes eigenes Marginkapital prüft das Marginbudget.
- Der signed isolierte Nettostand nach Funding bestimmt Equity,
  Initialmargin und Liquidationsstress.
- Gebühren und negative Fundingzahlungen verbrauchen das eigene Kostenbudget.
  Credits erneuern dieses Budget nicht und erhöhen keine Kapitalzuordnung.
- Noch aus isoliertem Principal bezahlte, nicht tatsächlich wiederhergestellte
  Fundingkosten bleiben zusätzlich im unposted Cash gedeckt.

Für einen vorgeschlagenen vollständigen Kauf zu seinem maximalen Fillpreis
werden neue Fees, Cash und kombinierter Durchschnitt projiziert.
Der tatsächliche erste Fill einer bestehenden Position bleibt eingefroren.
Strikte isolierte Deckung bis−50% dieses ersten Fills, korrelierter
Kontostress mit allen freien Kostenreserven,6% bestätigte Tagesbasis und
8% ursprüngliches Startkapital bleiben verbindlich.
Die Mindestdeckungsanzeige bezeichnet hier den benötigten **Nettostand**,
nicht zusätzlich zu transferierende Margin.

Aktuelle unsichere Positionen lassen sich nicht durch eine hypothetische neue
Kaufmargin genehmigungsfähig rechnen. Vollständige frische Marks, aktuelle
UTC-Tagesbasis, Raster/Mindestorder, eigene Kosten-/Marginbudgets und gebundene
Revision bleiben erforderlich. Normale Abschlussverluste können neue volle
Budgets sperren, ohne einen permanenten Kontohalt zu erfinden.

## Reservierung und Abgleich

Pro Forschungskonto gibt es konservativ höchstens **einen** ausstehenden
Kaufintent. Die Reservierung bindet Konto/Plan, unveränderlichen Request,
Maximalpreis, Menge, zusätzliche Margin, Feeobergrenze und Intentidentität.
Sie verändert noch keine Cash-/Position-/Kostenbuchung. Die gesamten freien
Basketbudgets waren schon vor dieser Reservierung gedeckt; eine zweite
Cashabbuchung für dieselbe Reserve wäre falsch.

Ein unversuchter Intent kann lokal aufgehoben werden, seine ID bleibt
verbraucht. Nach `record_order_attempt` ist der Ausgang ausdrücklich unklar.
Das ist eine Zustandsbuchung, **keine Dispatchgenehmigung**. Es gibt keine
automatische Wiederholung, keine Freigabe durch Zeitablauf und keinen lokalen
Storno, der einen unklaren Brokerauftrag als endgültig gelöscht behandelt.
Solange ein Intent besteht, sperrt er neue Käufe auch für andere Baskets.

Tatsächliche Teilfills benötigen qualifizierte Brokerorder-/Fillidentitäten.
Jeder Fill wird einmal gebucht; bereits mit dem ersten Fragment gestellte
Margin muss beim nächsten nicht erneut transferiert werden. Restliche Margin-
und Feereserven werden um tatsächlich gebuchte Beträge vermindert.
Mark, Tagesbasis, Funding und belegte Marginpostings dürfen während eines
unklaren Auftrags weiter gebucht werden; die konservative Ledgerreihenfolge
wird nicht umgangen.

Eine terminale `OrderResolution` bindet Intent und Order sowie exakt die
bereits gebuchte kumulative Menge, Margin und Fees. Ein bloßer Timeout,
ein offener Status oder fehlende Fillfragmente lösen den Intent nicht.
Ein teilgefüllter, nachweislich stornierter Auftrag bleibt als Position
gebucht; nur seine ausstehende Reservierung endet. Vor dem nächsten Intent
wird der gesamte aktuelle Stand erneut geprüft.

Bekannte Fills jenseits reservierter Menge/Margin/Fees/Preis/Hebeleinstellung
oder ohne passenden Intent werden trotzdem gebucht. Eine zusätzliche
Abgleichsperre bleibt dauerhaft bestehen, auch nach Terminalbestätigung
oder Kursgewinn. Diese Sperre steht getrennt von den unveränderten
Ledger-v1-Halts; die ursprüngliche Ledgerhashkette wird nicht umgeschrieben.
Tatsächliche Exits erhalten ebenfalls Fill-Deduplizierung.

## Herkunfts- und Betriebsgrenzen

Ein Revisions-/Hashkettenwrapper bindet Änderungen und alle verbrauchten IDs.
Die Deduplizierung gilt **innerhalb dieser erhaltenen Forschungszustandslinie**,
auch bei neuer Revision, geändertem Body oder anderem Ordernamen.
IDs müssen vom späteren Adapter über Broker/Konto/Symbol eindeutig qualifiziert
werden. Je Identitätsliste sind höchstens1024 Einträge möglich; volle Listen
sperren neue Intents und werden niemals automatisch geleert. Das ist ein
begrenztes Testmodell, kein langlebiger Journalspeicher.

`start_pending_research` nimmt einen bereits vertrauenswürdig abgeglichenen
Ledger an. Es ist kein Restorepfad: ein neuer Wrapper über demselben Ledger
beweist keine früheren IDs oder fehlenden Orders. Konstruktoren und
Evidenzdigests sind vertrauenswürdige Eingaben, keine Brokerbeweise.
Alle Events müssen chronologisch sortiert sein; verspätete Brokerlieferungen
oder unbekannte DB-Commits brauchen später einen dauerhaften Abgleich.
In-Memory-Revisionsprüfung ist noch keine DB-CAS.

Die Vollfillprojektion zum Maximalpreis beweist **nicht jede mögliche
Teilfillpreisfolge**. Ein günstigeres erstes Fragment setzt insbesondere
einen niedrigeren−50%-Stresspreis für spätere Fragmente. Der ursprüngliche
Researchbefund darf daher weder als laufende Ordergenehmigung noch als
Nachweis sicherer restlicher Fills wiederverwendet werden. Ein Test hält
diesen Unterschied ausdrücklich fest: nach tatsächlichen Fragmenten wird
der nächste Kauf am echten ersten Fill gesperrt.
IP-067 muss vor einer Fortsetzungs-/Dispatchintegration die verbleibende
Fillhülle und konservative Gapdeckung kausal prüfen.

Rechtzeitige Wirksamkeit des eigenen Puffers bei Brokerhebel2× bleibt ebenso
offen. Keine automatische Nachschuss-/Hebelleiter, kein vollständiges
historisches Funding-/Fee-/Maintenanceprofil, keine Leistungsbehauptung.
Kein JSON-/HTTP-/DB-/Broker-/Runtimecaller; `execution_enabled=false`.

## Abnahme und nächster Schritt

28 neue synthetische Fälle für Reservierungen, unklare Outcomes,
Teilfills, Terminalsummen, semantische Fillreplays, Funding, brutto/netto
Kapital, normal verlorene Budgetdeckung, Gapbuchungen und7 Slots.
246 unterschiedliche Hostfälle bestanden (245 Vollsuite plus neue
First-fragment-Prüfung innerhalb28 gezielter Fälle).
250 unterschiedliche gepinnte Trading-/Workerfälle mit167 Subtests bestanden
(249 Vollsuite plus neuer Grenzfall gezielt). Eigenprüfung; keine zusätzliche
Agentdelegation oder unveränderte Credentials-/DB-/Publicregression.
Keine Dependencies/Migrationen oder öffentlichen Container geändert.

IP-067 ergänzt inzwischen kausale Restfill-/Gapstressprüfung.
[Vertrag und Endpunktgrenzen](futures-continuation-stress.md).
Signal-/Replay-/Zyklusadapter ist durch [IP-068](futures-signal-replay.md) ergänzt.
Vollständige tatsächliche Fundingarchive,
historische Kontraktannahmen und exakte Regime-/Budgetaufteilung bleiben
IP-055/063/BL-030. Bestehende Dreijahresdaten und reservierter Holdout bleiben
unverändert; noch kein neuer Futuresnetto-Backtest.
