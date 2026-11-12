# Eigene Cashkosten und aktive Basket-Ranges

IP-079 korrigiert die zwei in IP-078 nachgewiesenen Finanzierungsbremsen.
Das neue Forschungsprofil `isolated-usdt-capital-cash/2` ist ausdrücklich
getrennt vom unveränderten historischen `isolated-usdt-capital-ladder/1`.
Protokoll vor dem erneuten Marktvergleich:
`research-protocols/futures-capital-cash-20261112.json`,
SHA256 `1dfc67d29dcc5f89e72a610d43823b7041470810f10e3757d7fd2d135effb4fa`.

Gebuchte Fundinggutschriften bleiben im eigenen isolierten Basket. Sie können
spätere Fundingbelastungen decken. Als Kostenbudgetverbrauch zählen sämtliche
Ein-/Ausstiegsgebühren plus das Maximum aus bereits tatsächlich aus eigener
Kostenreserve nachgeschossener Margin, negativem Nettofunding und null.
Eine bereits gezahlte Restoration bleibt bis zum Abschluss eigenes ausgegebenes
Cash; spätere Gutschriften machen daraus kein verfügbares Kontocash.
Der historische Bruttozähler bleibt für Audit und alte Profile erhalten.
Auch die tatsächliche Kostenüberschreitung beim Abschluss bleibt ein Hardstop.

Vor jedem Kauf muss das ungestellte Cash die vollständige verbleibende
Eigenkapitalstaffel, ungenutzte Kostenreserve und noch aus eigener Kostenreserve
zu restaurierende Fundingdebits aller aktiven sowie des neu beantragten Baskets
decken. Leere, nicht beantragte Slots haben keinen Kapitalanspruch.
Nach einem Verlust unterhalb 2000 USDT können bei 10000 Startkapital deshalb
vier unverändert große 2000-USDT-Ranges verfügbar sein; ein fünfter Einstieg
wartet auf ausreichendes Cash. Bestehende Ranges werden nicht verkleinert.
Liquidierte Ranges bleiben terminal mit reserviertem ungestelltem Staffelkapital;
keine automatische Wiederaufnahme oder Nutzung fremder Basketmargin.

Fünf automatische RSI-Käufe und sechste manuelle Reserve, Eigenkapitalvolumen,
konstanter Baskethebel, initiale Margin, aktuelle Liquidation und −55%-Exit
bleiben unverändert. 6%/8% bleiben Warnungen. Es gibt keine neue KI, privaten
Brokerorders, Reinvestition oder Holdoutauswertung.

Der Vergleich verwendet dieselben fünf Coins, native Dreijahresdaten und
alle zehn vorher eingefrorenen Gebühren-/Hebel-/Schutz-/Preisablaufvarianten.
Aufruf: `python3 infra/scripts/backtest-futures-capital.py --cash-budgets NEW_OUTPUT_DIRECTORY`.
Vollständige Journals werden aus Genesis wiederhergestellt; der Erfolgsbeleg
bindet Daten-, Protokoll-, Implementations- und Ergebnisdateien.
Ausgangsergebnisse werden nicht überschrieben. Höherer Profit ist kein
Korrektheitskriterium; entscheidend sind finanzierbare, regelkonforme Abläufe.

160 unterschiedliche gezielte gepinnte Tests mit 101 Subtests bestanden:
Kapital-/Range-/Fundingregressionen, Ledger/Risiko, Signal und Journal sowie
Wirtschaftsprofil und vollständiger neuer synthetischer Marktpfad.
Der Vergleich protokolliert finanzielle Ablehnungen getrennt von den
Signalfiltern an frischen H4-Grenzen; diese Zähler sind Diagnose, keine neue
Einstiegsautorität. Keine breite Credential-/DB-/Frontend-Testwiederholung.
