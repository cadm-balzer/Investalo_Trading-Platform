# Integrationen — geplanter Bereich

Bitget: BTC/USDT und ETH/USDT Spot ohne Hebel auf H4 sind bestätigt.
Account-/API-Familie und Capabilities vor Adapterimplementierung prüfen.
MT5: bestehende EAs als Referenz; authentifizierte nutzereigene Terminalbridge
mit lokalem Journal und Abgleich. Keine laufenden Referenzsysteme ändern.
Startstrategie ist XAUUSD Trend/Pullback H1/M15 nach unabhängiger Validierung.
MT5 läuft laut Nutzer auf einem separaten Heimnetzserver. Neue Bridge ausgehend
über authentifiziertes HTTPS zum zentralen Einstieg, ohne eingehende Routerports.
Getrenntes Brokerdemo und feste Konto-/Gerätebindung: `docs/mt5-bridge.md`.

Markt-, News- und Makrodaten benötigen geprüfte Nutzungsrechte und Quoten.
Details: `docs/architecture.md`, `docs/trading.md`, `docs/sources.md`.
