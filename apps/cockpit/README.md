# Cockpit — geplanter Bereich

Responsives Portfolio-Cockpit, Konten und Positionen, Strategien, Backtests,
Tradingjournal, Marktinformationen sowie Benutzer- und Credentialeinrichtung.
Next.js/React/TypeScript sind als Grundstack bestätigt, noch nicht installiert.

Verträge kommen aus `packages/contracts/`. Keine Brokerkeys im Browser, keine
Orderentscheidungen im Frontend. Details: `docs/concept.md`, `docs/architecture.md`.
Manueller Crypto-Paperpuffer mit Vorschau, Bestätigung und serverseitigem Risk Gate;
Nutzerinformation bestätigt: einmalige Cockpitmeldung nach fünfter Stufe,
optionale E-Mail; manuelle Freigabe gemäß Q29 mit 5%-Preisbedingung.
Echte KI und vollständige News-/Kalenderfeeds folgen nach dem bestätigten M1.
