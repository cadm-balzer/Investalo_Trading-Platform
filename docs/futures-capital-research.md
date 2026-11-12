# Futures-Kapitalprofil mit festen Baskethebeln

IP-073,2026-11-12: Q41–Q43 als eigener, reiner Offline-Kapitalkern.
`futures_capital_research.py` nutzt bestehende Margin-/Kostenrechnung,
den Ereignisledger und vollständige immutable Ereignisidentitäten.
Keine Brokerverbindung, Runtimeaktivierung oder Marktperformance.
Der bestehende Branch enthält IP-072 und die anschließenden Entscheidungen;
Main`d749081` enthält diese noch nicht, daher im bestehenden Branch fortgesetzt.

## Eigenkapital und Hebel

`CapitalPlan` bindet den eigenen Versions-/Plandigest, vollständige Kontrakte,
Kostenbudgets und originalen Kontostart. Gleichmäßige Budgetplanung mit
expliziter Kostenquote und Geldraster; fünf reguläre Stufen und eine manuelle
Reserve wachsen25%. Keine zusätzliche Pufferabzweigung aus der Staffel.
Die1%-Kostenquote ist eine Annahme, keine Zusicherung ausreichender
Funding-/Liquidationskostendeckung, insbesondere bei höherem Nominal.

Nach einem normalen vollständigen Abschluss erhält der nächste Basketzyklus
eine frische Kostenreserve. Bereits bezahlte Gebühren bleiben im Cash und
Nettoergebnis; sie werden nicht erstattet. Eine tatsächliche Überschreitung
der alten Reserve bleibt als Budgetfehler erfasst. Liquidierte Slots bleiben
gesperrt und erhalten keine automatische neue Reserve.

`freeze_basket_leverage` erfasst pro Symbol/Zyklus genau eine erklärte
2×–10×-Entscheidung vor dem ersten Kauf. Weitere Käufe halten diesen Hebel
fest. Nach normalem Abschluss kann der nächste Zyklus eine neue Entscheidung
bekommen. Es gibt keinen AI-Aufruf; der Evidenzdigest ist vertrauenswürdiger
Forschungseingang, keine Signatur-/AI-Autorität.

`prepare_capital_entry` erzeugt aus Stufenkapital×Hebel eine auf das
Kontraktraster abgerundete Menge. Es prüft ausschließlich Kapitalbedingungen.
RSI/Rearm/5%-Abstand, Schutzstopps und authentifizierte manuelle Freigabe
sind noch separat anzuschließen; dieser Kapitalkern erteilt keine
Handelserlaubnis. Die automatische API verweigert Stufe6.

## Warnungen und tatsächlich notwendige Deckung

6% Tages-/8% ursprünglicher Startverlust sind Warnungen; gemeinsamer
−50%-Kontostress und mögliche hypothetische Stressliquidation bleiben
Diagnosen. Sie erzwingen keine Käufe oder Schließungen und sperren die
geplanten Nachkäufe nicht allein.

Eigenbudgets, Kosten, frische vollständige Marks, UTC-Tagesbasis,
Kontraktraster/-limits und tatsächliche Initialmargin bleiben erforderlich.
Die Initialmargin des neuen Modells nutzt den tatsächlichen Positions-
Einstand beziehungsweise den höheren aktuellen Mark, nicht den alten
First-fill-Preis einer inzwischen verbilligten Position. Das ist eine
deklarierte Modellrechnung, keine historische Broker-Abrechnungsreplik.
Der First-fill-Anker bleibt für die getrennte−50%-Stressdiagnose erhalten.

`simulate_capital_fill` ist ausdrücklich ein vollständiges synthetisches
Fillmodell. Es bindet den unveränderten State/Assessment, aktuelle Deckung,
Preislimit und vollständige Ereignishistorie. Keine Broker-Teilfills,
Unknownorders oder Persistenzautorität. Funding nur mit expliziten
Ereignissen und gleichzeitiger Markbewertung buchen. Zusätzliche Margin
aus Nachkaufreserven wird abgewiesen; ausdrücklich belegte Wiederherstellung
von zuvor für Kosten belastetem Principal ist separat möglich.

## Liquidation ohne Phantomkapital

Eine aktuell gefährdete Position erscheint in `liquidation_required`.
Neue Käufe warten auf ihre Abrechnung; die Gefahr allein beendet nicht
sämtliche anderen Baskets. `LiquidationSettlement` enthält vollständige
Schließmenge, Ausführungspreis, Gebühr, zurückgezahlte Margin, einen
ausdrücklich belegten Versicherungsbetrag und terminalen Evidenzdigest.
Diese Angaben müssen im36-stelligen Modell exakt zusammenpassen.
Kein automatisch angenommener Versicherungsbetrag/Nullsaldo.

`LiquidatedBasket.net_pnl` berücksichtigt gegebenenfalls den ausdrücklich
belegten Versicherungsbetrag; kein negativer Gapbetrag wird still abgeschnitten.
Das ist eine Forschungsbuchung und kein Nachweis realer Brokerhaftung.
Der liquidierte Zyklus bleibt gesperrt, keine automatische Wiederbelegung.
Seine ungestellten Staffelbeträge bleiben reserviert. Verlorene gestellte
Margin wird jedoch nicht erneut als volle zukünftige Budgetreserve angesetzt:
andere korrekt gedeckte Baskets bleiben nutzbar. Tatsächliche Kosten-/
Budgetüberschreitungen werden weiterhin gebucht und als Fehlerzustand erfasst.

## Kompatibilität und nächste Integration

Legacypläne behalten ihre harten6%/8%/−50%-Prüfungen. Separate Planidentität,
defaultneutrale Ledger-Hooks und ausdrückliche Ablehnung des neuen Plans im
alten Pending-/Signaladapter verhindern vermischte Profile.
Sieben ökonomische Legacyzustände gegen den akzeptierten HEAD-Ledger
(Kauf/Marks/Funding/Kostenrestoration/Exit) reproduzieren exakt dieselben Digests.

Neue24 synthetische Fälle: bestätigte Kapitalwerte, drei parallele volle
Staffeln über Warnschwellen, unveränderter Zyklushebel, neue Zyklusentscheidung,
Funding/Kosten, eigene Liquidation, Restmargin/Versicherungsabgleich,
unverbrauchte Reserven, Fremd-/Stale-/Doppelergebnisse und Kapazitätsgrenzen.
35 abgeschlossene Zyklen belegen frische Kostenreserven ohne Gebührenerstattung.
Erster gepinnter Futureslauf293 Fälle/379 Subtests inklusive22 neuer Fälle;
danach87 Kapital-/Pending-/Signalfälle/34 Subtests einschließlich
des23. neuen Falls und21 Langpending-/Journalfälle/17 Subtests grün.
Abschließend55 Kapital-/Ledgerfälle/37 Subtests einschließlich des24. neuen
Falls grün; sieben Legacydigests erneut identisch.
295 unterschiedliche gepinnte Fälle insgesamt; Überschneidungen nicht
addieren. Keine breiten Credential-/DB-/API- oder alten Spotmarktläufe.

IP-074 verbindet inzwischen RSI-/Nachkaufsignale mit diesem Kapitalkern
und separatem geschlossenem H1/H4-Supertrend einschließlich Vorrang
bekannter Liquidation; [Signaladapter](futures-capital-signals.md).
Native Futures-H1-/Fundingkohorte und wirtschaftliche Ausführung bleiben
einzufrieren. Vor tatsächlicher langer
Marktleistung vollständigen Journalrestore und benötigte Identitätskapazität
für die gewählte Preisachse nachweisen. Die heutige State-/Merklewurzel ist
kein Restore. Holdout unverändert gesperrt; keine AI-/Paper-/Liveaktivierung.
