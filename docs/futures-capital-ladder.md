# Eigenkapitalstaffel und akzeptierte Futuresliquidation

Q42,2026-11-12. Nutzer bestätigt: Tabellenbeträge sind echtes Eigenkapital
je Einstieg. Der Hebel bestimmt daraus das Kaufnominal. Höherer Hebel kann
zur Liquidation führen, bevor fünf reguläre Käufe ausgeführt sind; dieses
Risiko ist für die neue Forschungsvariante ausdrücklich akzeptiert.
Das ersetzt die frühere Garantieanforderung, jeden Fillstand ohne weitere
Käufe gegen−50% abzudecken. Kein Echtgeld-/Liveauftrag.

## Kapitalrechnung

10000 USDT, drei Slots, je3333,33333333 Gesamtbudget.
Sechsstufen-Eigenkapitalpool3300,33003300 und Kostenreserve33,00330033.
Fünf reguläre Käufe, sechste Stufe nur manuell. Gewichte1,25^0..1,25^5;
vollständige Beträge auf0,00000001 abrunden. Nachstehend auf Cent gerundet.
Die bestehende1%-Kostenreserve ist eine Planungsgröße, keine belegte
Deckung sämtlicher Futuresgebühren/Funding-/Liquidationskosten.

| Stufe | Eigenkapital | Kaufnominal2× | Kaufnominal5× | Kaufnominal10× |
|---|---:|---:|---:|---:|
| 1 | 293,13 | 586,27 | 1465,67 | 2931,34 |
| 2 | 366,42 | 732,83 | 1832,09 | 3664,17 |
| 3 | 458,02 | 916,04 | 2290,11 | 4580,21 |
| 4 | 572,53 | 1145,05 | 2862,63 | 5725,27 |
| 5 | 715,66 | 1431,32 | 3578,29 | 7156,58 |
| 6, nur manuell | 894,57 | 1789,15 | 4472,86 | 8945,73 |

Nominalspalten stammen aus den ungerundeten Eigenkapitalbeträgen.
Gleicher Eigenkapitaleinsatz bleibt bei jedem Hebel erhalten; keine
Umverteilung zwischen Einstiegskapital und unbestimmtem zusätzlichen Puffer.
Nicht verwendete Stufen bleiben reserviert und werden nicht automatisch
als isolierte Sicherheiten gestellt. Keine Nachschüsse anderer Baskets.
Broker-Mengenraster/Fillpreise können tatsächliche Kaufwerte reduzieren.
Bei einem bestehenden Kontrakt betreffen Änderungen der Brokerhebeleinstellung
die gesamte Position; pro Fill berechnetes Kaufnominal ist keine getrennte
Brokerposition mit eigener Liquidationsgrenze.

## Neue Forschungsregeln

- Q41:6%/8% berichten als Warnschwellen, gemeinsamen−50%-Kontostress als
  Diagnose. Keine Kaufblockade/Erzwangsschließung aus diesen Schwellen.
- Q42: hypothetische Liquidation bei einem späteren−50%-Stress wird als
  Risiko ausgewiesen, verhindert aber nicht allein den Einstieg.
- Tatsächlich fehlende Initialmargin, aktuelle Liquidation, verbrauchtes
  Eigenbudget, unklare Orders und ungültige Daten bleiben reale Grenzen.
  Keine Weiterkäufe oder erfundene Erholung einer liquidierten Position.
- Historische Liquidation mit tatsächlichem Terminalstand, Gebühren und
  Funding verbuchen; ungenutzte Kaufstufen nicht als bereits verlorene
  Margin ausgeben. Die automatische Slotwiederbelegung nach Liquidation
  ist nicht freigegeben; bisherigen Risikofallstatus erhalten.
- H4-RSI/Rearm/5%-Abstand/25%-Staffel, manuelle Stufe6,+5%-Schutzaktivierung,
  Nettofloor und gewünschter H1-Supertrend bleiben.−55% ist ein Kursnotausstieg,
  der eine zuvor eintretende Liquidation nicht verhindern kann.

Diese Richtung ist dokumentiert, aber bisherige Rechenkerne/Replayprofile
sind noch nicht umgestellt. Alle alten eingefrorenen Ergebnisse bleiben
historische Referenz. Keine AI-Hebelwahl oder Marktperformance behauptet.

## Mechanisches Beispiel mit vorhandenem Rechenkern

Lesende Berechnung mit `PoolPlan`, `LongPosition`, `MarginSchedule` und
`liquidation_bound`; keine neuen Module oder Marktdaten.
Erster Kaufpreis100, folgende reguläre Kaufpreise95/90,25/85,7375/
81,450625. RSI-Signale werden ausschließlich für dieses Rechenbeispiel
als rechtzeitig vorhanden angenommen. Konstanter Hebel, isoliert nur
ausgeführte Stufenmargin, kein zusätzlicher Puffer/Funding, Maintenance0,5%
und Schutzreserve für Closefees0,1%. Entryfees werden separat aus der
Kostenreserve bezahlt, entsprechend dem bestehenden Forschungsrechner.
Dies sind deklarierte synthetische Annahmen, keine historischen Brokertarife
oder Aussagen zur realen Abrechnung. `liquidation_bound` ist eine konservative
Modellgrenze einschließlich Schutzreserve, kein exakter Brokerpreis.

| Hebel | Erreichte reguläre Käufe | Letzte Modellgrenze | −55%-Kursnotausstieg |
|---|---:|---:|---:|
| 2× | 5 | 44,282902 | 45 |
| 5× | 5 | 70,852643 | 45 |
| 10× | 4 | 82,534159 | 45 |

Bei10× wird nach Stufe4 die Modellgrenze82,534159 erreicht, bevor der
fünfte Kaufpreis81,450625 erreicht wird. Gestellte Stufenmargin1690,09875224,
noch nicht gestellte Reststaffel1610,23128073. Die Reststaffel rettet die
Position in diesem Beispiel nicht automatisch. Auch bei2× liegt nach dem
ersten Kauf die Modellgrenze50,301811 über45; fünf frühere Nachkäufe sind
kein garantierter Schutz, wenn deren RSI-Signale oder Ausführung fehlen.
Die erste2×-Stufe braucht keine spontane−50%-Bewegung, um bei anhaltendem
Abwärtstrend vor dem−55%-Notausstieg die Modellgrenze zu erreichen.
Keine Rendite, Liquidationshäufigkeit oder Erholungswahrscheinlichkeit
aus diesem mechanischen Beispiel ableiten.

## Noch zu spezifizieren

AI-Hebel2×–10× aus zum Entscheidungszeitpunkt bekannten Marktdaten;
keine rückblickend perfekte Marktphase. Der AI-Filter ist später vorgesehen,
nicht Bestandteil der bisherigen Ergebnisse.
Nutzerfrage gestellt: Hebel beim Basketstart festlegen oder vor jedem
Nachkauf neu bewerten? Empfehlung für das erste Profil: je Basket einfrieren.
Illustrative konstante Hebel sind keine bereits bestätigte AI-Regel.
Vor Marktleistung passendes natives Futures-H1-/Funding-/Kostenprofil
einfrieren und alle gewählten Hebelvarianten einschließlich Liquidationen
berichten. Bestehender Holdout bleibt geschützt.
