# Ursachen der verbleibenden H1-Futures-Kaufablehnungen

IP-083: der vollständige unveränderte IP-082-Journalbestand ist erneut
restauriert. Alle109440 Commands, der abschließende Receipt,530 tatsächliche
Käufe und581 Einstiegskandidaten stimmen exakt. Kein neuer Backtest,
keine Änderung der Performance oder wirtschaftlichen Regeln.

## Versuche und tatsächliche spätere Käufe

| Ablehnungsgründe eines Versuchs | Versuche | Gleiche Stufe im selben Zyklus später ausgeführt |
|---|---:|---:|
| Nur Preisgrenze | 22 | 21 |
| Nur deklarierte Initialmargin | 19 | 19 |
| Beide Gründe | 10 | 10 |
| Gesamt | 51 | 50 |

Die Gründe werden überlappend gezählt:32 Preisgrenzentreffer plus29
Initialmargintreffer sind51 Versuche. Sie betreffen34 unterschiedliche
Coin-/Basketzyklus-/Stufenkombinationen;33 davon wurden später tatsächlich
ausgeführt. Mehrere Ablehnungsversuche können zum selben späteren Fill gehören.
Der spätere Fill ist keine zusätzliche simulierte Order.

Für die Zuordnung wurden alle530 tatsächlich gespeicherten `entry`-Commands
gelesen. Die Reihenfolge tatsächlicher erster Stufen je Coin ergibt den
Zyklus; alle271 Zyklusidentitäten stimmen mit den269 Abschlussdatensätzen
und den zwei offenen Endbaskets überein. Jeder zugeordnete Fill liegt nach
der Ablehnung und besitzt einen konkreten Journalzeitpunkt und Sequenzanker.
[Spätere tatsächliche Fills](research-protocols/futures-capital-admission-fill-followup-20261113.json).

## Die reinen Marginablehnungen sind Rundungsreste

Alle19 ausschließlich wegen Initialmargin abgelehnten Versuche betreffen
XRP, acht unterschiedliche Zyklus-/Stufenkombinationen. Fehlbeträge:
**0,000000000376911191307543 bis0,000000007376838495785480 USDT**.
Alle liegen unter dem Geldquantum1E−8.

Funding wurde bezahlt und aus eigener Barreserve weitgehend restauriert.
Der Restorationbetrag wird abgerundet; ein kleiner isolierter Restfehlbetrag
bleibt bestehen. Die neue Kaufmenge wird ebenfalls abgerundet. Bei XRP reicht
der dadurch ungenutzte kleine Nominalrest nicht immer aus, um die exakt
verglichene deklarierte Initialmargin zu decken.
Die verbleibende zulässige eigene Restorationkapazität beträgt dabei
**7,7667 bis14,0104 USDT**. Es handelt sich in diesen nativen Fällen weder um
aufgebrauchte Kostenreserve noch um einen großen unfinanzierten Nachkauf.
Alle betroffenen Stufen wurden später ausgeführt.

Beispiel XRP-Zyklus7/Stufe2,2022-10-13T10:00:02+00:00:
nach Sequenz7238 fehlen0,000000007376838495785480 USDT;
eigene Restorationkapazität13,9508986019212202100 USDT.
Trade/Mark beide0,4547; Kaufgrenze0,45492735. Die Preisgrenze ist eingehalten.
Der vorangegangene synthetische Test beweist zusätzlich den anderen,
hier nicht beobachteten Fall echter Fundingdepletion bei erschöpfter
Restorationkapazität. Diese beiden Fälle dürfen nicht verwechselt werden.

Ein weiterer XRP-Stufe2-Versuch besitzt denselben kleinen Marginrest und
zusätzlich einen Preisgrenzentreffer. Insgesamt20 der29 Marginablehnungen
betreffen Rundungsreste unter1E−8.

## Preisgrenze gegenüber dem Markkurs

Alle32 Preisgrenzentreffer entstehen, weil der beobachtete Markkurs über
der maximalen Kaufgrenze `Trade ×1,0005` liegt. Der Mehrabstand beträgt
0,04394 bis51,16403 Basispunkte, also maximal rund0,51164%.
Das ist der Abstand **oberhalb der bereits um0,05% erhöhten Kaufgrenze**.
Die Buy-Fillannahme verwendet den Tradepreis; die deklarierte Margin verwendet
den größeren Basis-/Marknominalwert. Dieser Guard ist eine Forschungsregel,
keine belegte historische Brokerablehnung.

Neun dieser Versuche betreffen erste Käufe und erzeugen zugleich größere
deklarierte Marknominal-Marginfehlbeträge bis0,899873819926184 USDT.
Sie haben weder offene Fundingdepletion noch einen bestehenden Basketverlust.
Alle neun ersten Kaufstufen wurden später tatsächlich ausgeführt.

Beispiel SOL-Zyklus6/Stufe1,2022-11-08T21:00:02+00:00:
nach Sequenz10072 Trade23, Mark23,1292361, Kaufgrenze23,0115.
Der Abstand oberhalb der Kaufgrenze beträgt51,16403 Basispunkte;
deklarierter Fehlbetrag0,899873819926184 USDT.

Nur eine betroffene Stufe wurde bis Forschungsende nicht ausgeführt:
XRP-Zyklus49/Stufe5,2025-04-09T04:00:02+00:00, nach Sequenz99375.
Trade1,7469, Mark1,7483, Kaufgrenze1,74777345;
ausschließlich Preisgrenze. Es wird kein hypothetischer Gewinn aus diesem
entgangenen Kauf berechnet.

## Belege und nächster Schritt

[Vollständige Evidence](research-protocols/futures-capital-admission-audit-evidence-20261113.json),
SHA256 `198c9a3ac87b92f141b6583113731842980ade9f989a62601c86940ebb9ee305`.
[Erfolgsreceipt](research-protocols/futures-capital-admission-audit-receipt-20261113.json),
SHA256 `4e4b5bf91f13cd8771c0f18b051d28b79305a34e4e8695ea90f3d0faa8d5c86b`.
Fill-Followup-SHA256
`5db21db2a7caac23d87d7c89c5c37fb89e1df414f2e6f139dcc5a42121d1efe0`.
Vier unveränderte Originalartefakte und zehn Start-/Endimplementationshashes
(acht Originale, zwei Diagnosedateien) geprüft.2782 Ausführungspässe,
keine zusätzlichen Buchungen. Neun unterschiedliche gepinnte Tests und
zehn Subtests bestanden; Exportfix und betroffene Fälle gezielt nachgeprüft.
Unterbrochene/fehlgeschlagene Verzeichnisse bleiben ohne Erfolgsreceipt erhalten.

Als Nächstes Geldquantisierung, echte Broker-Margin-/Preisregeln und
Kosten-/Mengenraster getrennt kalibrieren. Die derzeitige exakt-dezimale
Restoration/Marginkombination ist bei XRP eine Modellbremse. Der neue Vergleich
muss eigene belegte Annahmen und einen eingefrorenen Referenzanker erhalten.
Keine stille Toleranz, erfundene Margin oder Verwendung anderer/manueller
Kapitalreserven. Unabhängiger Holdout und AI-Regime-/Hebelfreigabe bleiben offen.

IP-082 bleibt netto+9579,93 USDT/DD17,62%, ohne Kontohaltes oder Liquidationen.
Der Diagnosebefund beweist keinen Mehrgewinn durch Regeländerungen oder AI.
[Diagnosevertrag](futures-admission-audit.md).
