"""Operator-only invitation binding. No self-registration or implicit privilege change."""
import argparse
from uuid import UUID, NAMESPACE_URL, uuid5

from .database import connect
from .settings import Settings


def provision(
    settings: Settings, *, issuer: str, subject: str, tenant_name: str,
    role: str, tenant_id: UUID | None = None,
) -> tuple[UUID, UUID]:
    if not issuer.startswith("https://") or not 1 <= len(subject) <= 255:
        raise ValueError("An HTTPS issuer and confirmed opaque OIDC subject are required")
    if not 1 <= len(tenant_name) <= 120 or role not in ("owner", "trader", "researcher", "viewer"):
        raise ValueError("Invalid tenant name or role")
    with connect(settings) as db:
        if db.execute("SELECT current_user AS name").fetchone()["name"] != "investalo_migration":
            raise ValueError("Provisioning requires investalo_migration")
        db.execute("SELECT pg_advisory_xact_lock(724809362)")
        db.execute(
            "INSERT INTO platform.users(oidc_issuer,oidc_subject) VALUES (%s,%s) "
            "ON CONFLICT(oidc_issuer,oidc_subject) DO NOTHING", (issuer, subject),
        )
        user = db.execute(
            "SELECT id,active FROM platform.users WHERE oidc_issuer=%s AND oidc_subject=%s",
            (issuer, subject),
        ).fetchone()
        if not user["active"]:
            raise ValueError("Inactive identity requires a separately reviewed recovery")
        if tenant_id is None:
            # Equal names belonging to other users never join their tenants implicitly.
            tenant_id = uuid5(NAMESPACE_URL, f"investalo:{user['id']}:{tenant_name}")
            db.execute(
                "INSERT INTO platform.tenants(id,name) VALUES (%s,%s) ON CONFLICT(id) DO NOTHING",
                (tenant_id, tenant_name),
            )
        tenant = db.execute(
            "SELECT name FROM platform.tenants WHERE id=%s", (tenant_id,),
        ).fetchone()
        if not tenant or tenant["name"] != tenant_name:
            raise ValueError("Explicit tenant identity does not match")
        membership = db.execute(
            "SELECT role,active FROM platform.memberships WHERE tenant_id=%s AND user_id=%s",
            (tenant_id, user["id"]),
        ).fetchone()
        if membership and (membership["role"] != role or not membership["active"]):
            raise ValueError("Existing membership differs; privilege changes require separate review")
        if not membership:
            db.execute(
                "INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES (%s,%s,%s)",
                (tenant_id, user["id"], role),
            )
        return user["id"], tenant_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--tenant-name", required=True)
    parser.add_argument("--role", choices=("owner", "trader", "researcher", "viewer"), required=True)
    parser.add_argument("--tenant-id", type=UUID)
    args = parser.parse_args()
    user_id, tenant_id = provision(Settings.from_environment(), **vars(args))
    print(f"Invitation bound: user_id={user_id} tenant_id={tenant_id}")


if __name__ == "__main__":
    main()
