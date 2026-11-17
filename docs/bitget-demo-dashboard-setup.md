# Bitget-Demo-Einrichtung im Cockpit

Stand 2026-11-17, IP-009/IP-015. Sicherheit und Kontozugänge verlinken jetzt
einen eigenen Bereich unter `/security/credentials/demo`. Der Link auf der
Sicherheitsstartseite bleibt auch bei nicht erreichbarer Overview-API sichtbar.
Anmeldung bleibt erforderlich. Die gesperrte Seite erklärt Demo-Keyerstellung,
Passkeybestätigung und spätere Eingabe von API-Key, Secret und Passphrase.
Der bestehende Browserpfad unterstützt reine Leserechte. Das
[Demo-Handelskeyprofil](bitget-demo-trading-profile.md) prüft und verschlüsselt
Handelskeys separat; seine dauerhafte Dashboardanbindung fehlt noch.
Noch keine echte Schlüsseleingabe.

## Tatsächlicher Betriebsstand

Am17.11. ausschließlich Containerdatum, Routenvorhandensein und Schema gelesen:

- Laufende Cockpit-/API-Container vom2026-11-09; Cockpit enthält die kompilierte
  Demo-Seite noch nicht.
- Datenbank `investalo`: `platform.schema_migrations`001–012. Demo014–017
  bisher nur in der isolierten Credentialfixture;013 gehört zum Futures-Paperpfad.
- `demoCredentialBrowserRuntimeAvailable()` fest `false`, normaler
  Browseradapter ohne ausführenden Provider. Isolierte Abnahme mit
  synthetischen Schlüsseln aktiviert keinen öffentlichen Zugang.

Ein Merge verändert weder Container noch Schema. Die neue Sichtbarkeit ist
kein Nachweis einer funktionsfähigen nativen Schlüsselregistrierung.

## Nächste Freischaltung

1. Nutzer bestätigt Demo-Erstellung und Futures-/Spot-Read-Write am17.11.
   Eigene Handelsprofilanbindung verwenden und native Rechte separat prüfen.
   Keine Schlüssel im Chat, PR, Kommandoargument oder Log entgegennehmen.
2. Tatsächliches Demo-Konto/UID/Parent/IP/Rechte an aktuellen Plattformnutzer
   binden. Originalen privaten Herkunfts-/Provisioningvertrag beibehalten;
   Fixtureidentitäten und synthetische Tripleannahme nicht übernehmen.
3. Eigene private Signier-/Verschlüsselungs-/mTLS-Identitäten, eingeschränkte
   Service-/DB-Rollen und ausführenden Browserprovider/native Provisioner
   installieren. Vorhandenen unveränderten additiven Migrationssatz und
   Passkey-/Demo-API-Opt-ins am tatsächlichen Betriebsstand vorprüfen.
4. Echte Dashboardregistrierung, Widerruf und unbekannten Commitabschluss
   abnehmen. Ein Flag allein erfüllt diese Schritte nicht.
5. Konkreten öffentlichen Rollout nach Projektregel separat genehmigen
   lassen. Frontendaktualisierung und echte Keyfreischaltung getrennt
   ausweisen. Demo-Orders benötigen danach vollständige Konto-/Order-/
   Cash-/Kostenabnahme.

Dieser Checkpoint ändert Navigation und Texte. Keine Migration,
Runtimefreischaltung, Dienstneuerstellung oder native Bitget-Anfrage.

## Prüfung

Gepinnter Cockpit-Build und Typecheck erfolgreich.58 gezielte Node-Fälle
im netzlosen Container bestanden: tatsächliches SSR der gesperrten Demo-Seite,
sichtbarer Sicherheitseinstieg auch beim Overview-Ausfall, bestehende
Mandanten-/Assetprüfung und Ablehnung privater Requestbodies vor Aufnahme
bei gesperrtem Demo-HTTP-Adapter. Keine physische Browser-/native Keyabnahme.
