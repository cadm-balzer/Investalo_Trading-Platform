"""Offline issuer tests: every DB/container/SMTP boundary is mocked."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("verified_mail_issuer", ROOT/"infra/scripts/issue-verified-passkey.py")
ISSUER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ISSUER)


class VerifiedMailIssuerTests(unittest.TestCase):
    def case(self, proof, *, existing="0"):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        local=Path(temporary.name)
        config=dict(schema=ISSUER.SCHEMA,origin="https://cockpit.investalo.de",
            tenantId=str(UUID(int=1)),userId=str(UUID(int=2)),subject=str(UUID(int=3)),
            recipient="owner@fixture.invalid")
        calls=[]
        def sql(q):
            return existing if "count(*)" in q else "4"
        def node(**kw):
            calls.append(("node",kw["network"] if "network" in kw else "none"))
            if kw.get("ticket"):
                return "synthetic handoff"
            if proof is None:
                raise ValueError()
            return json.dumps(proof)
        def run(args,source=None):
            calls.append(("issue",args))
            return ""
        def protected(path,*args):
            return json.dumps(config if path.name=="config" else {"token":"A"*43}).encode()
        with patch.object(ISSUER,"LOCAL",local), patch.object(ISSUER,"sql",sql), patch.object(ISSUER,"node",node), \
            patch.object(ISSUER,"run",run), patch.object(ISSUER,"protected",protected), \
            patch.object(ISSUER.sys,"argv",["issuer","--issue-and-email"]), patch.object(ISSUER.os,"geteuid",return_value=0), \
            patch.object(ISSUER.os,"chown"), patch.object(ISSUER.os,"fchown"), \
            contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result=ISSUER.main()
        return result,calls,local

    def test_missing_or_foreign_email_evidence_never_issues_or_sends(self):
        for proof in (None,dict(reference=str(UUID(int=4)),email="foreign@fixture.invalid",epoch=4)):
            with self.subTest(proof=proof):
                result,calls,local=self.case(proof)
                self.assertEqual(result,1)
                self.assertFalse(any(c[0]=="issue" for c in calls))
                self.assertFalse((local/"platform-admin-tickets").exists())

    def test_existing_or_revoked_passkey_is_never_bootstrapped(self):
        result,calls,_=self.case(dict(reference=str(UUID(int=4)),email="owner@fixture.invalid",epoch=4),existing="1")
        self.assertEqual(result,1)
        self.assertEqual(calls,[])

    def test_actual_verified_reference_binds_issuance_and_private_handoff(self):
        result,calls,local=self.case(dict(reference=str(UUID(int=4)),email="owner@fixture.invalid",epoch=4))
        self.assertEqual(result,0)
        issued=[c[1] for c in calls if c[0]=="issue"]
        self.assertEqual(len(issued),1)
        self.assertIn("--email-confirmed",issued[0])
        self.assertIn(str(UUID(int=4)),issued[0])
        self.assertEqual(calls[-1],("node","investalo-local_mail_submission_egress"))
        self.assertTrue((local/"platform-admin-tickets"/str(UUID(int=4))/"delivery-acknowledged").exists())


if __name__=="__main__":
    unittest.main()
