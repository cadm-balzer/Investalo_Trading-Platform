# Infrastruktur — geplanter Bereich

Private Entwicklung zuerst. Zentraler TLS-Einstieg, interne Datenbank und
Worker, getrennte Serviceidentitäten, verschlüsselte Backups und geprüfter
Wiederanlauf sind Anforderungen. Docker Compose und lokales Authelia sind
bestätigt. Der private Nutzerkreis soll schon im Pilot einen öffentlichen
zentralen HTTPS-Einstieg erhalten; DB und Worker bleiben intern. Vorhandener
kostenloser SMTP und administratives E-Mail-Recovery sind bestätigt.
Pilotbackupziele RPO 24h/RTO 4h mit verschlüsselten externen/offline Kopien;
Pins, konkrete Ziele und Laufzeitnachweise stehen aus. Keine Rolloutfreigabe.

Noch keine lauffähige Deploymentkonfiguration.
Details: `docs/operations.md`, `docs/security.md`.
