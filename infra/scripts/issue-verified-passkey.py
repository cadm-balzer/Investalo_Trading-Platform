#!/usr/bin/env python3
"""Issue/deliver one first Passkey ticket from actual encrypted email evidence.

SMTP password, confirmation code and ticket never appear in args/env/output.
Original passkey_admin is used only after real code verification. No mail
attestation is inferred from an operator flag or a chat answer.
"""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "infra/local"
SCHEMA = "investalo-platform-admin/1"


def run(args, source=None):
    p = subprocess.run(args, input=source, capture_output=True, text=True, timeout=60)
    if p.returncode:
        raise ValueError()
    return p.stdout.strip()


def sql(query):
    return run(["bash",str(ROOT/"infra/scripts/compose.sh"),"exec","-T","postgres","psql",
        "--no-psqlrc","--username","investalo_admin","--dbname","investalo",
        "--tuples-only","--no-align","--set","ON_ERROR_STOP=1","--command",query])


def protected(path, uid, mode):
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError()
    value=path.lstat()
    if not stat.S_ISREG(value.st_mode) or value.st_uid!=uid or stat.S_IMODE(value.st_mode)!=mode or value.st_nlink!=1 or not 1<=value.st_size<=8192:
        raise ValueError()
    return path.read_bytes()


def node(*, source, network="none", arguments=(), ticket=None):
    args=["docker","run","--interactive","--pull","never","--rm","--network",network,"--read-only",
        "--cap-drop","ALL","--security-opt","no-new-privileges","--user","10002:10002",
        "--mount",f"type=bind,source={LOCAL/'platform-admin'},target=/run/platform-admin,readonly",
        "--mount",f"type=bind,source={LOCAL/'cockpit-public-data'},target=/app/state,readonly",
        "--mount",f"type=bind,source={ROOT/'apps/cockpit/src'},target=/verification-src,readonly"]
    if ticket:
        args += ["--mount",f"type=bind,source={ticket},target=/run/passkey-ticket,readonly"]
    args += ["--entrypoint","node","investalo-cockpit:0.1.0-local",
             "--experimental-strip-types","--input-type=module","-",*arguments]
    return run(args,source)


def main():
    try:
        if sys.argv[1:]!=["--issue-and-email"] or os.geteuid()!=0:
            raise ValueError()
        config=json.loads(protected(LOCAL/"platform-admin/config",10002,0o400))
        if config["schema"]!=SCHEMA or config["origin"]!="https://cockpit.investalo.de":
            raise ValueError()
        tenant,user=(str(UUID(config[k])) for k in ("tenantId","userId"))
        subject=str(UUID(config["subject"]))
        epoch=sql(f"""SELECT u.auth_epoch FROM platform.users u JOIN platform.memberships m ON m.user_id=u.id
          WHERE u.id='{user}' AND m.tenant_id='{tenant}' AND u.active AND m.active AND m.role='owner'
          AND u.oidc_issuer='https://auth.cockpit.investalo.de' AND u.oidc_subject='{subject}';""")
        if not epoch.isdigit():
            raise ValueError()
        if sql(f"SELECT count(*) FROM platform.passkey_credentials WHERE user_id='{user}' AND tenant_id='{tenant}';")!="0":
            raise ValueError()
        proof=json.loads(node(arguments=(epoch,),source="""
import {loadMailAuthority,mailStore} from '/verification-src/lib/admin-mail-authority.ts';
const m=await loadMailAuthority();
const proof=await mailStore(m,'/app/state').confirmation(Number(process.argv[2]),Math.floor(Date.now()/1000));
console.log(JSON.stringify(proof));
"""))
        reference=str(UUID(proof["reference"]))
        if proof["email"]!=config["recipient"] or proof["epoch"]!=int(epoch):
            raise ValueError()
        directory=LOCAL/"platform-admin-tickets"/reference
        directory.parent.mkdir(mode=0o700,exist_ok=True)
        parent=directory.parent.lstat()
        if not stat.S_ISDIR(parent.st_mode) or parent.st_uid!=0 or stat.S_IMODE(parent.st_mode)!=0o700:
            raise ValueError()
        directory.mkdir(mode=0o700)  # Repeated/unknown issuance requires reconciliation, never retry.
        os.chown(directory,10003,10003)
        ticket=directory/"ticket.json"
        run(["bash",str(ROOT/"infra/scripts/compose.sh"),"run","--rm","--no-deps","-T",
            "--volume",f"{directory}:/passkey-output","migrate",
            "python","-m","investalo_api.passkey_admin","issue",
            "--tenant-id",tenant,"--user-id",user,"--rp-id","cockpit.investalo.de",
            "--auth-epoch",epoch,"--ttl-seconds","600","--output-file","/passkey-output/ticket.json",
            "--email-confirmed","--confirmation-reference",reference])
        raw=protected(ticket,10003,0o600)
        delivery=directory/"mail-ticket.json"
        fd=os.open(delivery,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
        with os.fdopen(fd,"wb") as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno());os.fchown(stream.fileno(),10002,10002)
        marker=directory/"delivery-pending"
        fd=os.open(marker,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o400)
        with os.fdopen(fd,"w") as stream:
            stream.write(reference);stream.flush();os.fsync(stream.fileno())
        acknowledgement=node(ticket=delivery,network="investalo-local_mail_submission_egress",arguments=(epoch,reference),source="""
import {readFile} from 'node:fs/promises';
import {loadMailAuthority,mailStore} from '/verification-src/lib/admin-mail-authority.ts';
import {sendPasskeyTicket} from '/verification-src/lib/admin-smtp.ts';
const m=await loadMailAuthority(),ticket=JSON.parse(await readFile('/run/passkey-ticket','utf8'));
const now=Math.floor(Date.now()/1000),epoch=Number(process.argv[2]),reference=process.argv[3];
if(ticket.tenant_id!==m.authority.tenantId||ticket.user_id!==m.authority.userId||
  ticket.auth_epoch!==epoch||ticket.rp_id!=='cockpit.investalo.de'||
  Date.parse(ticket.expires_at)<=now*1000)throw new Error('Ticket rejected');
await mailStore(m,'/app/state').deliverTicket(epoch,now,reference,ticket.token,sendPasskeyTicket);
console.log('Ticket SMTP handoff acknowledged.');
""")
        if acknowledgement!="Ticket SMTP handoff acknowledged.":
            raise ValueError()
        os.rename(marker,directory/"delivery-acknowledged")
        print("Passkey ticket issued from verified email evidence and sent. Ticket remains private; no automatic retry.")
        return 0
    except Exception:
        print("Passkey issuance/delivery not confirmed. Private artifacts retained; reconcile before any retry.",file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
