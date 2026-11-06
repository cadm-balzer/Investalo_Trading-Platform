# Infrastruktur — geplanter Bereich

Private Entwicklung zuerst. Zentraler TLS-Einstieg, interne Datenbank und
Worker, getrennte Serviceidentitäten, verschlüsselte Backups und geprüfter
Wiederanlauf sind Anforderungen. Docker Compose und lokales Authelia sind
bestätigt. Der private Nutzerkreis soll schon im Pilot einen öffentlichen
zentralen HTTPS-Einstieg erhalten; DB und Worker bleiben intern. Vorhandener
kostenloser SMTP ist vorgesehen. Pins, E-Mail-Recovery und Backupziele bleiben
zu konkretisieren; es gibt keine Rolloutfreigabe.

Noch keine lauffähige Deploymentkonfiguration.
Details: `docs/operations.md`, `docs/security.md`.
