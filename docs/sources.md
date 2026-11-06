# Offizielle Quellen und Best-Practice-Abgleich

Prüfdatum: 2026-11-06. Nur öffentliche Dokumentation recherchiert; keine
Credentials oder privaten Kontodaten an Anbieter übermittelt.
Anbieterregeln/Quoten vor Implementierung und Livefreigabe erneut prüfen.

| Thema | Offizielle Quelle | Relevanz |
|---|---|---|
| PostgreSQL RLS | https://www.postgresql.org/docs/current/ddl-rowsecurity.html | Default-deny, Owner-/Superuser-Bypass, `WITH CHECK`, Grenzen |
| Tenantkontext | https://www.postgresql.org/docs/current/sql-set.html | `SET LOCAL` endet mit der Transaktion |
| PITR | https://www.postgresql.org/docs/current/continuous-archiving.html | Basebackup/WAL; `pg_dump` allein nicht ausreichend |
| OAuth | https://www.rfc-editor.org/rfc/rfc9700.html | PKCE, Redirect-/Token-/Refreshschutz |
| MFA | https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html | Phishingresistenz und sichere Recovery |
| Secrets | https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html | Least privilege, Rotation, Audit und Lifecycle |
| AI-Agenten | https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html | Begrenzte Tools und Rechte |
| Prompt Injection | https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html | Externe Inhalte als untrusted Daten |
| Outbox | https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html | Atomare Übergabe; Consumer müssen Duplikate behandeln |
| FastAPI Deployment | https://fastapi.tiangolo.com/deployment/concepts/ | Prozess-/Speicherbedarf, HTTPS, Neustarts |
| Next.js Self-hosting | https://nextjs.org/docs/app/guides/self-hosting | Reverse Proxy, Cache und private Antworten |
| systemd Ressourcen | https://www.freedesktop.org/software/systemd/man/latest/systemd.resource-control.html | cgroup-Limits und Ressourcenpriorität |
| systemd Isolation | https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html | Dienstidentitäten und Prozess-/Dateisystemschutz |
| Docker Ubuntu | https://docs.docker.com/engine/install/ubuntu/ | Ubuntu 26.04 unterstützt; veröffentlichte Ports können UFW umgehen |
| Compose Produktion | https://docs.docker.com/compose/how-tos/production/ | Single-Server-Betrieb möglich, zusätzliche Hardeningkonfiguration nötig |
| Authelia systemd | https://www.authelia.com/integration/deployment/bare-metal/ | Fertiger lokaler OIDC-/MFA-Provider mit systemd-Beispielen |
| Authelia Nutzer | https://www.authelia.com/configuration/first-factor/introduction/ | Keine interne öffentliche Registrierung |
| Authelia Passwort | https://www.authelia.com/configuration/first-factor/file/ | Argon2-Speicherbedarf bei parallelen Logins |
| Authelia OIDC | https://www.authelia.com/configuration/identity-providers/openid-connect/clients/ | Zwei-Faktor-Clientpolicy und PKCE |
| Authelia Sessions | https://www.authelia.com/configuration/session/introduction/ | Memory-/Redis-Sessionoptionen |
| Authelia WebAuthn | https://www.authelia.com/configuration/second-factor/webauthn/ | Alleiniger Passkey nicht pauschal als stabile MFA werten |
| ZITADEL Free | https://zitadel.com/pricing/detail | Freefeatures, Quoten und kurze Log-/Auditfristen |
| ZITADEL Mail | https://zitadel.com/docs/guides/manage/console/default-settings | Eingebauter SMTP für Evaluation, produktiven Mailweg klären |
| ZITADEL Datenschutz | https://zitadel.com/docs/legal/data-processing-agreement | Externe Verarbeitung vor Providerwahl prüfen |
| Keycloak Kapazität | https://www.keycloak.org/server/containers | 2 GB Empfehlung für kleinen produktionsfähigen IdP allein |
| authentik Kapazität | https://docs.goauthentik.io/install-config/install/docker-compose/ | Mindestens 2 CPU/2 GB Host-RAM |
| MT5 Python | https://www.mql5.com/en/docs/python_metatrader5/mt5initialize_py | Bindung an Terminalprozess |
| MT5 OrderSend | https://www.mql5.com/en/docs/trading/ordersend | Annahme ist kein vollständiger Fillnachweis |
| MT5 Events | https://www.mql5.com/en/docs/event_handlers/ontradetransaction | Tradeevents für Ausführungsabgleich |
| MT5 Symbolregeln | https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants | Lots, Stops, Handelsstatus und Kontrakte |
| Bitget Rechte | https://www.bitget.com/docs/classic/rest-api | Keyrechte, Passphrase und IP-Bindung |
| Bitget UTA | https://www.bitget.com/docs/uta/uta-intro | Accountmodi nicht implizit festlegen |
| Bitget Orders | https://www.bitget.com/docs/catalog/classic-contract-trade/classic-contract-trade | `clientOid`, Abfrage und Reduce-only-Besonderheiten |
| Bitget Positionen | https://www.bitget.com/docs/catalog/classic-contract-position/classic-contract-position | Margin, Liquidation und Positionsdaten |
| Bitget Liquidation | https://www.bitget.com/futures/introduction/liquidation-summarize | Markpreis und Maintenance-Risiko |
| Bitget Market | https://www.bitget.com/docs/catalog/classic-contract-market/classic-contract-market | Instrumentregeln und Fundingdaten |
| FTMO Objectives | https://ftmo.com/en/trading-objectives/ | Kontoprofile/Phasen unterscheiden sich bei Verlustregeln |
| FTMO News | https://ftmo.com/en/faq/can-i-trade-news/ | Restriktionen abhängig von Phase/Konto |
| FTMO Swing | https://ftmo.com/en/faq/ftmo-swing-account-type/ | Separates Profil nötig |
| FTMO Personal Use | https://ftmo.com/en/forbidden-trading-practices/ | Drittzugriff und übermäßige Handelsänderungen prüfen |
| Alpha Vantage | https://www.alphavantage.co/support/ | Free derzeit 25 Requests/Tag; kein vollwertiger Livefeed |
| Twelve Data Preise | https://twelvedata.com/pricing | Basic derzeit 8 APIcredits/Minute, 800/Tag; Entitlements beachten |
| Twelve Data Credits | https://support.twelvedata.com/en/articles/5615854-credits | Gewicht pro Endpoint/Symbol und Quotenreset |
| TradingView API | https://www.tradingview.com/support/solutions/43000474413-i-need-access-to-your-api-in-order-to-get-data-or-indicator-values/ | Kein allgemeiner Nutzerdaten-API-Zugang |
| TradingView Terms | https://www.tradingview.com/policies/ | Display-/Non-display-Nutzung einschließlich automatisierten Handels beschränkt |
| Marke | https://www.investalo.de/ | Geforderte Stylingreferenz, keine fertige Designspezifikation |

## Auswirkungen auf den Entwurf

- RLS ergänzt Autorisierung; ein privilegierter Backenddienst bleibt eine eigene
  Sicherheitsgrenze.
- Outbox und Command-IDs unterstützen Konsistenz, versprechen aber keine
  Exactly-once-Ausführung beim Broker.
- MT5 braucht einen verfügbaren Terminalhost, keinen generischen REST-Adapter
  ohne lokale Laufzeit.
- Marginstress muss aktuelle Brokerregeln verwenden; die Beispielrechnung ist
  keine Liquidationsgarantie.
- TradingView Essentials wird nicht als genehmigter Feed für automatischen
  Handel eingeplant. Vertrags-/Anbieterprüfung wäre dafür erforderlich.
- Free-Datenabos begrenzen Abdeckung und Frequenz. Für Mehrnutzeranzeige und
  Kundendienstleistungen sind Nutzungs-/Redistributionsrechte separat zu prüfen.

Die konsultierte Outbox-Dokumentation begründet ein Muster, keine Auswahl von AWS
als Infrastruktur. Ebenso ist die Nennung einer Chart-/Authlösung noch keine
Installation oder Providerfreigabe.
