"""Read secret files explicitly; libpq TLS settings remain authoritative."""
from dataclasses import dataclass, field
import os
from pathlib import Path


def secret_file(variable: str) -> str | None:
    location = os.getenv(variable)
    if not location:
        return None
    value = Path(location).read_text(encoding="utf-8").rstrip("\r\n")
    if not value:
        raise ValueError(f"{variable} points to an empty secret")
    return value


@dataclass(frozen=True)
class Settings:
    internal_key: str | None = field(default=None, repr=False)
    oidc_issuer: str | None = None
    passkey_rp_id: str | None = None
    database_password: str | None = field(default=None, repr=False)
    database_parameters: dict[str, str] = field(default_factory=dict, repr=False)
    passkey_credential_authorizations: bool = False
    passkey_origin: str | None = None
    paper_status_preview: bool = False
    futures_paper_settings_preview: bool = False

    @classmethod
    def from_environment(cls) -> "Settings":
        key = secret_file("API_INTERNAL_AUTH_SECRET_FILE")
        if key is not None and len(key.encode("utf-8")) < 32:
            raise ValueError("Internal authentication key must contain at least 32 bytes")
        parameters = {
            parameter: os.environ[variable]
            for variable, parameter in (
                ("PGHOST", "host"), ("PGPORT", "port"), ("PGDATABASE", "dbname"),
                ("PGUSER", "user"), ("PGSSLMODE", "sslmode"),
                ("PGSSLROOTCERT", "sslrootcert"),
            )
            if variable in os.environ
        }
        return cls(
            internal_key=key,
            oidc_issuer=os.getenv("API_OIDC_ISSUER"),
            passkey_rp_id=os.getenv("API_PASSKEY_RP_ID"),
            database_password=secret_file("PGPASSWORD_FILE"),
            database_parameters=parameters,
            passkey_credential_authorizations=os.getenv("API_PASSKEY_CREDENTIAL_AUTHORIZATIONS") == "1",
            passkey_origin=os.getenv("API_PASSKEY_ORIGIN"),
            paper_status_preview=os.getenv("API_PAPER_STATUS_PREVIEW") == "1",
            futures_paper_settings_preview=os.getenv("API_FUTURES_PAPER_SETTINGS_PREVIEW") == "1",
        )

    def connection_parameters(self) -> dict[str, str | int]:
        parameters: dict[str, str | int] = dict(self.database_parameters)
        parameters["connect_timeout"] = 3
        if self.database_password is not None:
            parameters["password"] = self.database_password
        return parameters
