"""Explicit separate Demo trading-key provisioning; fixed identity GET only."""
import hashlib
import hmac
from uuid import UUID

from investalo_bitget import OwnerContext
from investalo_bitget.demo_trading_identity import ALLOWED, REQUIRED, trading_identity
from investalo_bitget.futures_demo import digest

from .bitget_payload import encode_credentials
from .demo_native_provisioning import (
    ORIGIN, DemoNativeProvisioner, DemoOriginApproval, DemoProvisioningRejected,
    PrivateDemoOriginReader, _canonical, _key,
)
from .demo_trading_secret import DemoTradingSecretSpec, PURPOSE

SCHEMA = "investalo-demo-trading-origin-approval/1"


def _trading_mac(record, credentials, key):
    metadata = _canonical({name: value for name, value in record.items() if name != "credential_mac"})
    return hmac.new(_key(key), b"investalo.demo.trading.origin-approval/1\0" +
        len(metadata).to_bytes(4, "big") + metadata +
        encode_credentials(credentials).reveal(), hashlib.sha256).hexdigest()


class DemoTradingOriginApproval(DemoOriginApproval):
    __slots__ = ()
    _schema = SCHEMA
    _allowed = ALLOWED
    _required = REQUIRED
    _credential_mac = staticmethod(_trading_mac)


def make_demo_trading_origin_record(*, credentials, provenance_key, owner, account_id,
        broker_uid, parent_uid, egress_ip, authorities, attestation_id,
        approved_ms, expires_ms, created_in_bitget_demo_mode):
    try:
        if (created_in_bitget_demo_mode is not True or type(owner) is not OwnerContext
                or type(account_id) is not UUID or type(attestation_id) is not UUID):
            raise ValueError()
        record = dict(schema=SCHEMA, origin=ORIGIN, attestation_id=str(attestation_id),
            tenant_id=str(owner.tenant_id), user_id=str(owner.user_id), account_id=str(account_id),
            broker_uid=broker_uid, parent_uid=parent_uid, egress_ip=egress_ip,
            authorities=authorities, approved_ms=approved_ms, expires_ms=expires_ms)
        record["credential_mac"] = _trading_mac(record, credentials, provenance_key)
        wire = _canonical(record)
        DemoTradingOriginApproval(wire)
        return wire
    except Exception:
        raise DemoProvisioningRejected() from None


class PrivateDemoTradingOriginReader(PrivateDemoOriginReader):
    __slots__ = ()
    _approval = DemoTradingOriginApproval


class DemoTradingNativeProvisioner(DemoNativeProvisioner):
    """Separate result type cannot be registered by the old read-only executor."""
    __slots__ = ()
    _approval = DemoTradingOriginApproval
    _identity = staticmethod(trading_identity)
    _evidence_schema = "investalo-demo-trading-provisioning-evidence/1"

    def _result(self, binding, approval, evidence):
        evidence = dict(evidence, purpose=PURPOSE, authorities=list(approval.authorities),
                        order_execution_enabled=False)
        return DemoTradingSecretSpec(binding=binding, parent_uid=approval.parent_uid,
            egress_ip=approval.egress_ip, authorities=approval.authorities,
            provisioning_digest=digest(evidence), credential_revision=1)
