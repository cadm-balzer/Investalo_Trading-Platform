"""Own default-off launcher and synthetic intake guard; no real key material."""
import json
from uuid import uuid4

import pytest
from investalo_credential_store import demo_trading_acceptance_runtime as own
from investalo_credential_store.request_assertion import OnboardingRejected


def fields():
    return dict(schema=own.SCHEMA, tenant_id=str(uuid4()), user_id=str(uuid4()),
        account_id=str(uuid4()), uncertain_account_id=str(uuid4()),
        broker_uid="123456789", uncertain_broker_uid="123456790",
        signing_sha256="a"*64, kek_sha256="b"*64, client_certificate_sha256="c"*64,
        provisioning_digest="d"*64)


def test_default_and_wrong_optin_open_no_files_or_port(monkeypatch, capsys):
    monkeypatch.setattr(own, "_read", lambda *args, **kwargs: pytest.fail("file intake must not run"))
    monkeypatch.setattr(own, "create_private_asgi_server", lambda *args, **kwargs: pytest.fail("port must not open"))
    for argv in ([], ["--development"], ["--synthetic-demo"], ["--synthetic-demo-trading", "extra"]):
        assert own.main(argv) == 1
    assert capsys.readouterr().err == (own.ERROR + "\n")*4


def test_own_config_does_not_accept_normal_schema_shared_signer_or_same_accounts():
    for change in (dict(schema="investalo-credential-development-service/1"),
                   dict(schema="investalo-demo-credential-acceptance/1"),
                   dict(kek_sha256="a"*64), dict(signing_sha256="untrusted")):
        with pytest.raises(own.DemoTradingAcceptanceRejected):
            own.DemoTradingAcceptanceConfig({**fields(), **change})
    value = fields()
    for original, alias in (("account_id", "uncertain_account_id"), ("broker_uid", "uncertain_broker_uid")):
        with pytest.raises(own.DemoTradingAcceptanceRejected):
            own.DemoTradingAcceptanceConfig({**value, alias: value[original]})


def test_synthetic_register_and_keyless_revoke_are_the_only_allowed_inputs():
    config = own.DemoTradingAcceptanceConfig(fields())
    base = dict(platform_account_id=str(config.account_id), connection_id=str(uuid4()))
    triple = dict(api_key=own.API_KEY, secret=own.SECRET.decode(), passphrase=own.PASSPHRASE)
    own.synthetic_request(config, "register", json.dumps({**base, "credentials": triple}).encode())
    own.synthetic_request(config, "revoke", json.dumps({**base, "expected_revision": 1, "expected_storage": 1}).encode())
    for action, value in (
        ("register", {**base, "credentials": {**triple, "api_key": "actual-broker-key-must-be-rejected"}}),
        ("register", {**base, "platform_account_id": str(uuid4()), "credentials": triple}),
        ("replace", {**base, "credentials": triple, "expected_revision": 1, "expected_storage": 1}),
    ):
        with pytest.raises(OnboardingRejected, match="invalid_request"):
            own.synthetic_request(config, action, json.dumps(value).encode())
