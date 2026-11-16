"""Bounded isolated Demo HTTPS/BFF/API/PG/executor acceptance; synthetic only.

Host orchestration privately relays bounded RPC; the audit child has no bound
credential LOGIN password. Only the separate executor writes credentials.
"""
from contextlib import contextmanager
import base64
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import selectors
import socket
import ssl
import stat
import subprocess
import sys
from time import monotonic, time, sleep
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
OVERLAY = "infra/compose.demo-local-acceptance.yaml"
STATE = Path("/fixture-demo-acceptance")
ISSUER = "https://auth.cockpit.local.test:8443"
ORIGIN = "https://cockpit.local.test:8443"
ROLE = "investalo_credentials_tests_a"
MAX = 32768
CHECKS = 0
STAGE = "configuration"


class Failure(Exception):
    pass


def check(value):
    global CHECKS
    if not value:
        raise Failure()
    CHECKS += 1


def wire(value):
    raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
    check(len(raw) <= MAX)
    return raw + b"\n"


def emit(value):
    sys.stdout.buffer.write(wire(value))
    sys.stdout.buffer.flush()


def incoming():
    raw = sys.stdin.buffer.readline(MAX + 2)
    check(len(raw) <= MAX + 1 and raw.endswith(b"\n"))
    value = json.loads(raw)
    check(type(value) is dict)
    return value


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


@contextmanager
def exclusive_fixture():
    descriptor=os.open("/tmp/investalo-demo-local-acceptance",
                       os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    lock=None
    try:
        metadata=os.fstat(descriptor)
        check(stat.S_IMODE(metadata.st_mode)==0o700 and metadata.st_uid==10003)
        try:
            lock=os.open(".acceptance-lock",os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,
                         0o600,dir_fd=descriptor)
            os.fchown(lock,10003,10003)
            os.fsync(descriptor)
        except FileExistsError:
            lock=os.open(".acceptance-lock",os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=descriptor)
        metadata=os.fstat(lock)
        check(stat.S_ISREG(metadata.st_mode) and stat.S_IMODE(metadata.st_mode)==0o600
              and metadata.st_uid==10003 and metadata.st_nlink==1)
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:
        if lock is not None:
            os.close(lock)
        os.close(descriptor)


def child():
    from datetime import datetime, timedelta, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    import psycopg
    from psycopg.rows import dict_row
    from investalo_credentials import KEKRing, load_envelope
    from investalo_bitget import OwnerContext
    from investalo_bitget.futures_demo import DemoBinding
    from investalo_credential_store.demo_secret_provider import DemoSecretSpec, open_demo_secret
    from investalo_credential_store.demo_passkey_assertion import DemoPasskeyRequestVerifier
    from investalo_credential_store.passkey_request_assertion import PasskeyRequestContext
    from investalo_credential_store.demo_acceptance_runtime import SCHEMA, KEY_VERSION, API_KEY, SECRET, PASSPHRASE, EGRESS_IP
    global STAGE

    check(os.geteuid() == 10003 and os.environ["PGDATABASE"] == "investalo_credentials_checks")
    metadata = STATE.lstat()
    check(stat.S_ISDIR(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) == 0o700
          and metadata.st_uid == 10003 and metadata.st_gid == 10003)
    check((STATE / ".synthetic-demo-acceptance").read_bytes() == b"investalo-synthetic-demo-local-acceptance/1\n")

    @contextmanager
    def connect(runtime=False):
        user = os.environ["PGUSER"] if runtime else os.environ["API_TEST_ADMIN_USER"]
        password_file = os.environ["PGPASSWORD_FILE"] if runtime else os.environ["API_TEST_ADMIN_PASSWORD_FILE"]
        with psycopg.connect(host="postgres", port=5432, dbname="investalo_credentials_checks", user=user,
                password=Path(password_file).read_text().strip(), sslmode="verify-full",
                sslrootcert="/run/secrets/local_ca_cert", connect_timeout=5, row_factory=dict_row) as db:
            db.execute("SET LOCAL statement_timeout='10s'")
            db.execute("SET LOCAL lock_timeout='5s'")
            yield db

    tenant, user, account, uncertain, foreign_tenant, foreign_account = [uuid4() for _ in range(6)]
    subject = "synthetic-demo-acceptance-" + uuid4().hex
    run = str(uuid4())
    directory = STATE / run
    directory.mkdir(mode=0o700)
    for name in ("identity", "executor", "browser"):
        (directory / name).mkdir(mode=0o700)
    (directory / "executor/keks").mkdir(mode=0o700)

    def write(name, data):
        descriptor = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())

    def cbor(value):
        def header(major, size):
            return bytes([major * 32 + size]) if size < 24 else bytes([major * 32 + 24, size])
        if type(value) is int:
            return header(0 if value >= 0 else 1, value if value >= 0 else -1-value)
        if type(value) is bytes:
            return header(2, len(value)) + value
        return header(5, len(value)) + b"".join(cbor(key) + cbor(item) for key, item in value.items())

    private = ec.generate_private_key(ec.SECP256R1())
    numbers = private.public_key().public_numbers()
    public = cbor({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")})
    credential_id, user_handle, ticket, enrollment_binding = [secrets.token_bytes(32) for _ in range(4)]
    old_binding = None
    try:
        STAGE = "setup"
        with connect() as db:
            check(db.execute("SELECT current_database() AS database,session_user AS login").fetchone()
                  == {"database": "investalo_credentials_checks", "login": "investalo_migration"})
            check(db.execute("SELECT count(*) AS n FROM platform.schema_migrations").fetchone()["n"] == 17)
            old_binding = db.execute("SELECT tenant_id,user_id FROM platform.credential_role_bindings "
                                    "WHERE database_role=%s", (ROLE,)).fetchone()
            db.execute("INSERT INTO platform.tenants(id,name) VALUES(%s,'Synthetic Demo acceptance'),"
                       "(%s,'Synthetic foreign Demo')", (tenant, foreign_tenant))
            db.execute("INSERT INTO platform.users(id,oidc_issuer,oidc_subject) VALUES(%s,%s,%s)", (user, ISSUER, subject))
            db.execute("INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES(%s,%s,'owner')", (tenant, user))
            for own_tenant, own_account in ((tenant, account), (tenant, uncertain), (foreign_tenant, foreign_account)):
                db.execute("INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency,status)"
                           " VALUES(%s,%s,'Synthetic Demo acceptance','bitget','bitget_demo','USDT','ready')",
                           (own_tenant, own_account))
            db.execute("INSERT INTO platform.credential_role_bindings(database_role,tenant_id,user_id)"
                       " VALUES(%s,%s,%s) ON CONFLICT(database_role) DO UPDATE"
                       " SET tenant_id=excluded.tenant_id,user_id=excluded.user_id", (ROLE, tenant, user))
            db.execute("SELECT platform.passkey_issue_enrollment(%s,%s,%s,%s,%s,%s,%s,%s)",
                (tenant, user, "cockpit.local.test", ticket, user_handle, 0,
                 datetime.now(timezone.utc) + timedelta(seconds=300), uuid4()))

        def actor(db):
            for name, value in {"app.tenant_id": str(tenant), "app.user_id": str(user),
                    "app.oidc_issuer": ISSUER, "app.oidc_subject": subject}.items():
                db.execute("SELECT set_config(%s,%s,true)", (name, value))

        with connect(True) as db:
            actor(db)
            claimed = db.execute("SELECT * FROM platform.passkey_claim_enrollment(%s,%s,%s,%s,%s)",
                (ticket, "cockpit.local.test", enrollment_binding, 0, int(time()))).fetchone()
        with connect(True) as db:
            actor(db)
            record = db.execute("SELECT * FROM platform.passkey_finish_enrollment(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (claimed["claim_id"], enrollment_binding, credential_id, public, 0, False, False, 0, int(time()))).fetchone()
            check(record["storage_version"] == 1)

        STAGE = "identity"
        stamp = datetime.now(timezone.utc)
        ca_key = ec.generate_private_key(ec.SECP256R1())
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic isolated Demo acceptance CA")])
        ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
              .serial_number(x509.random_serial_number()).not_valid_before(stamp-timedelta(minutes=1))
              .not_valid_after(stamp+timedelta(hours=1)).add_extension(x509.BasicConstraints(ca=True,path_length=0), True)
              .add_extension(x509.KeyUsage(False,False,False,False,False,True,True,None,None),True)
              .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),False)
              .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),False)
              .sign(ca_key, hashes.SHA256()))

        def leaf(name, usage, server=False):
            key = ec.generate_private_key(ec.SECP256R1())
            builder = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,name)]))
                .issuer_name(ca_name).public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(stamp-timedelta(minutes=1)).not_valid_after(stamp+timedelta(hours=1))
                .add_extension(x509.BasicConstraints(ca=False,path_length=None),True)
                .add_extension(x509.KeyUsage(True,False,False,False,False,False,False,None,None),True)
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),False)
                .add_extension(x509.ExtendedKeyUsage([usage]),False))
            if server:
                builder = builder.add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]),False)
            cert = builder.sign(ca_key,hashes.SHA256())
            return key.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()), cert

        client_key, client_cert = leaf("synthetic-demo-bff",ExtendedKeyUsageOID.CLIENT_AUTH)
        executor_key, executor_cert = leaf("demo-executor.cockpit.local.test",ExtendedKeyUsageOID.SERVER_AUTH,True)
        browser_key, browser_cert = leaf("cockpit.local.test",ExtendedKeyUsageOID.SERVER_AUTH,True)
        signing, kek = secrets.token_bytes(32), secrets.token_bytes(32)
        api_secret = Path(os.environ["DEMO_ACCEPTANCE_API_SECRET_FILE"]).read_text().strip()
        pem = lambda cert: cert.public_bytes(Encoding.PEM)
        digest = lambda data: hashlib.sha256(data).hexdigest()
        for name, data in {
            "identity/signing-key": signing, "identity/executor-ca": pem(ca),
            "identity/client-certificate": pem(client_cert), "identity/client-private-key": client_key,
            "executor/signing-key": signing, "executor/client-ca": pem(ca),
            "executor/tls-certificate": pem(executor_cert), "executor/tls-private-key": executor_key,
            "executor/keks/active.key": kek, "browser/ca": pem(ca),
            "browser/certificate": pem(browser_cert), "browser/private-key": browser_key,
        }.items():
            write(name,data)
        broker_uid, uncertain_uid = (str(10**18+uuid4().int % (10**18)) for _ in range(2))
        provenance = digest(("synthetic-demo-acceptance/"+run).encode())
        runtime = dict(schema=SCHEMA,tenant_id=str(tenant),user_id=str(user),account_id=str(account),
            uncertain_account_id=str(uncertain),broker_uid=broker_uid,uncertain_broker_uid=uncertain_uid,
            signing_sha256=digest(signing),kek_sha256=digest(kek),
            client_certificate_sha256=digest(client_cert.public_bytes(Encoding.DER)),provisioning_digest=provenance)
        write("executor/config",json.dumps(runtime,separators=(",",":")).encode())
        session = dict(issuer=ISSUER,subject=subject,oidcAuthTime=int(time())-600,tenantId=str(tenant),
            authEpoch=0,expiresAt=int(time())+900,csrf=b64(secrets.token_bytes(32)),
            displayName="Synthetic Demo",tenantName="Synthetic Demo acceptance")
        bound = dict(handle=b64(secrets.token_bytes(32)),origin=ORIGIN,session=session)
        binding = digest(json.dumps(["passkey-action-proof-v1",bound["handle"],session["csrf"],ISSUER,subject,
            str(tenant),0,session["oidcAuthTime"],ORIGIN,session["expiresAt"]],separators=(",",":")).encode())
        spec = dict(schema="investalo-demo-credential-private-identity/1",directory="/run/demo-identity",ownerUid=10003,
            tenantId=str(tenant),userId=str(user),accountId=str(account),origin=ORIGIN,oidcIssuer=ISSUER,
            executorOrigin="https://demo-executor.cockpit.local.test:9443",signingSha256=digest(signing),
            caSha256=digest(pem(ca)),certificateSha256=digest(pem(client_cert)),privateKeySha256=digest(client_key),
            excludedSigningSha256=[digest(api_secret.encode()),digest(kek),digest(secrets.token_bytes(32))])
        emit(dict(kind="configuration",run=run,config=dict(bound=bound,spec=spec,account=str(account),
            uncertainAccount=str(uncertain),foreignAccount=str(foreign_account),internalKey=api_secret,
            credentialId=b64(credential_id),userHandle=b64(user_handle),
            privateKey=private.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()).decode(),
            api="https://demo-acceptance-api:8000",disabledApi="https://demo-acceptance-disabled-api:8000")))
        original_envelope = None
        audited = 0
        while True:
            message = incoming()
            if message["kind"] == "abort":
                break
            if message["kind"] == "ready":
                STAGE = "readiness"
                ctx = ssl.create_default_context(cadata=pem(ca).decode())
                ctx.load_cert_chain(directory/"identity/client-certificate",directory/"identity/client-private-key")
                deadline = monotonic()+45
                while True:
                    try:
                        with ctx.wrap_socket(socket.create_connection(("demo-executor.cockpit.local.test",9443),timeout=3),
                                server_hostname="demo-executor.cockpit.local.test") as channel:
                            channel.sendall(b"GET /unavailable HTTP/1.1\r\nHost: demo-executor.cockpit.local.test\r\nConnection: close\r\n\r\n")
                            check(b" 404 " in channel.recv(1024).split(b"\r\n",1)[0])
                        break
                    except ssl.SSLCertVerificationError:
                        STAGE = "readiness-certificate"
                        raise Failure() from None
                    except (OSError,ssl.SSLError):
                        if monotonic()>deadline:
                            raise Failure()
                        sleep(.2)
                STAGE = "readiness-api"
                api_tls=ssl.create_default_context(cafile="/run/secrets/local_ca_cert")
                for host in ("demo-acceptance-api","demo-acceptance-disabled-api"):
                    claims=dict(iss="investalo-bff",aud="investalo-api",sub=subject,oidc_iss=ISSUER,
                        oidc_auth_time=session["oidcAuthTime"],tenant_id=str(tenant),auth_epoch=0,
                        htm="GET",htu="/v1/passkeys/context",body_sha256=digest(b""),
                        iat=int(time()),exp=int(time())+30,jti=str(uuid4()))
                    segments=[b64(json.dumps(value,separators=(",",":")).encode()) for value in
                              (dict(alg="HS256",typ="JWT"),claims)]
                    unsigned=".".join(segments)
                    jwt=unsigned+"."+b64(hmac.digest(api_secret.encode(),unsigned.encode(),"sha256"))
                    with api_tls.wrap_socket(socket.create_connection((host,8000),timeout=12),
                                             server_hostname="api") as channel:
                        channel.sendall(("GET /v1/passkeys/context HTTP/1.1\r\nHost: "+host+
                            "\r\nAuthorization: Bearer "+jwt+"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n").encode())
                        check(b" 200 " in channel.recv(1024).split(b"\r\n",1)[0])
                emit(dict(kind="ready"))
                continue
            if message["kind"] == "complete":
                STAGE = "audit-counts"
                check(audited == 3)
                with connect() as db:
                    check(db.execute("SELECT count(*) AS n FROM platform.demo_passkey_credential_completion_audit "
                                     "WHERE tenant_id=%s", (tenant,)).fetchone()["n"] == 3)
                    check(db.execute("SELECT count(*) AS n FROM platform.passkey_credential_authorizations a "
                                     "JOIN platform.passkey_action_proofs p USING(proof_id) "
                                     "WHERE p.tenant_id=%s", (tenant,)).fetchone()["n"] == 0)
                    check(db.execute("SELECT count(*) AS n FROM platform.demo_credential_audit "
                                     "WHERE tenant_id=%s", (tenant,)).fetchone()["n"] == 3)
                emit(dict(kind="complete",checks=CHECKS,run=run))
                break
            check(set(message)=={"kind","action","token","body","uncertain"} and message["kind"]=="audit")
            STAGE = "audit-assertion"
            action, body = message["action"],message["body"].encode()
            request_context = PasskeyRequestContext(tenant_id=tenant,user_id=user,subject=subject,auth_epoch=0,
                oidc_auth_time=session["oidcAuthTime"],session_binding=binding,session_expires_at=session["expiresAt"])
            assertion = DemoPasskeyRequestVerifier(key=signing,oidc_issuer=ISSUER,origin=ORIGIN,clock=lambda:int(time())).verify(
                message["token"],action=action,body=body,context=request_context)
            own_account = uncertain if message["uncertain"] else account
            STAGE = "audit-completion"
            with connect() as db:
                row = db.execute("SELECT outcome,transaction_id FROM platform.demo_passkey_credential_completion_audit "
                    "WHERE authorization_id=%s",(assertion.authorization_id,)).fetchone()
                grant = db.execute("SELECT state,lock_transaction,receipt,consumed_jti FROM "
                    "platform.demo_passkey_credential_authorizations WHERE authorization_id=%s",(assertion.authorization_id,)).fetchone()
                check(row["outcome"]=="completed" and grant["state"]=="locked" and grant["consumed_jti"]==assertion.jti)
                check(row["transaction_id"]==grant["lock_transaction"])
                check(grant["receipt"]["body_sha256"]==digest(body) and assertion.oidc_auth_time==session["oidcAuthTime"])
                STAGE = "audit-storage"
                stored = db.execute("SELECT * FROM platform.demo_credential_connections "
                    "WHERE tenant_id=%s AND platform_account_id=%s",(tenant,own_account)).fetchone()
                expected = (1,2,"revoked") if action=="revoke" else (1,1,"active")
                check((stored["credential_revision"],stored["storage_version"],stored["status"])==expected)
                check(stored["user_id"]==user and stored["parent_uid"]=="0" and stored["egress_ip"]==EGRESS_IP)
                envelope_wire = json.dumps(stored["envelope"])
                check(SECRET.decode() not in envelope_wire and PASSPHRASE not in envelope_wire and API_KEY not in envelope_wire)
                STAGE = "audit-secret"
                secret_spec = DemoSecretSpec(binding=DemoBinding(OwnerContext(tenant,user),own_account,
                    stored["connection_id"],stored["broker_uid"]),parent_uid="0",egress_ip=EGRESS_IP,
                    provisioning_digest=provenance,credential_revision=1)
                ring = KEKRing(((KEY_VERSION,kek),),active_version=KEY_VERSION)
                decoded = open_demo_secret(load_envelope(envelope_wire),secret_spec,ring)
                check(decoded._api_key==API_KEY and decoded._secret_key==SECRET and decoded._passphrase==PASSPHRASE)
                if action=="register" and not message["uncertain"]:
                    original_envelope = stored["envelope"]
                if action=="revoke":
                    check(stored["envelope"]==original_envelope)
            audited += 1
            emit(dict(kind="audited",checks=CHECKS))
    finally:
        # CAS restoration of this test LOGIN binding only; append-only evidence stays.
        with connect() as db:
            current = db.execute("SELECT tenant_id,user_id FROM platform.credential_role_bindings"
                                " WHERE database_role=%s FOR UPDATE",(ROLE,)).fetchone()
            if current == {"tenant_id":tenant,"user_id":user}:
                if old_binding is None:
                    db.execute("DELETE FROM platform.credential_role_bindings WHERE database_role=%s",(ROLE,))
                else:
                    db.execute("UPDATE platform.credential_role_bindings SET tenant_id=%s,user_id=%s "
                        "WHERE database_role=%s",(old_binding["tenant_id"],old_binding["user_id"],ROLE))


def orchestrate():
    prefix=["bash","infra/scripts/compose.sh","--file",OVERLAY,"--profile","demo-local-acceptance"]
    owned=[]
    selector=selectors.DefaultSelector()
    buffers={}
    deadline=monotonic()+240
    run=None

    def start(service, run=None, rpc=False):
        name="investalo-demo-acceptance-"+uuid4().hex
        environment=os.environ.copy()
        environment.pop("DEMO_ACCEPTANCE_RUN",None)
        if run is not None:
            check(str(UUID(run))==run)
            environment["DEMO_ACCEPTANCE_RUN"]=run
        process=subprocess.Popen(prefix+["run","--rm","--no-deps","-T","--use-aliases","--name",name,service],
            cwd=ROOT,env=environment,stdin=subprocess.PIPE if rpc else subprocess.DEVNULL,
            stdout=subprocess.PIPE if rpc else subprocess.DEVNULL,stderr=subprocess.DEVNULL,bufsize=0)
        owned.append((process,name,service))
        if rpc:
            selector.register(process.stdout,selectors.EVENT_READ,process)
            buffers[process]=bytearray()
        return process

    def read(process):
        while b"\n" not in buffers[process]:
            check(monotonic()<deadline and process.poll() is None)
            for key,_ in selector.select(timeout=min(1,max(0,deadline-monotonic()))):
                owner=key.data
                raw=os.read(key.fileobj.fileno(),4096)
                if not raw:
                    selector.unregister(key.fileobj)
                    if owner is process and b"\n" not in buffers[owner]:
                        raise Failure()
                    continue
                check(len(buffers[owner])+len(raw)<=MAX+1)
                buffers[owner].extend(raw)
        raw,_,remaining=buffers[process].partition(b"\n")
        buffers[process]=bytearray(remaining)
        value=json.loads(raw)
        check(type(value)is dict)
        if value.get("kind")=="failed":
            # Report only fixed code-selected stages, never private diagnostics.
            allowed={"configuration","setup","identity","readiness","readiness-certificate","readiness-api","audit",
                     "audit-assertion","audit-completion","audit-storage","audit-secret","audit-counts",
                     "api-readiness","api-readiness-enabled","api-readiness-disabled","api-isolation","https-bff","bff-isolation",
                     "register","executor-restart","revoke","post-commit-unknown",
                     "register-prepare","register-proof","register-write",
                     "revoke-prepare","revoke-proof","revoke-write"}
            if value.get("stage") in allowed:
                print("Isolated Demo acceptance failed at "+value["stage"]+".",file=sys.stderr)
                for name in ("api_status","bff_status"):
                    if type(value.get(name)) is int and 100<=value[name]<=599:
                        print(name+"="+str(value[name]),file=sys.stderr)
                codes={"ENOTFOUND","EAI_AGAIN","ECONNREFUSED","ECONNRESET","ETIMEDOUT",
                       "ERR_TLS_CERT_ALTNAME_INVALID","UNABLE_TO_VERIFY_LEAF_SIGNATURE","CERT_HAS_EXPIRED",
                       "BOUNDED_TIMEOUT","INVALID_RESPONSE","BOUNDED_RESPONSE","none","other"}
                if value.get("network_code") in codes:
                    print("network_code="+value["network_code"],file=sys.stderr)
                if value.get("code") in {"Failure","TypeError","KeyError","AttributeError","OnboardingRejected",
                            "DemoSecretRejected","EnvelopeRejected","UndefinedColumn","UndefinedTable",
                            "OperationalError","TimeoutError","SSLCertVerificationError","other"}:
                    print("code="+value["code"],file=sys.stderr)
            raise Failure()
        return value

    def send(process, message):
        process.stdin.write(wire(message))
        process.stdin.flush()

    def inspect_owned():
        # Inspect actual containers, not just Compose source declarations.
        for process,name,service in owned:
            if process.poll() is not None:
                continue
            value=json.loads(subprocess.check_output(["docker","inspect",name],timeout=5))[0]
            options=value["HostConfig"]
            check(value["Config"]["User"]=="10003:10003" and options["ReadonlyRootfs"] is True)
            check(options["CapDrop"]==["ALL"] and "no-new-privileges:true" in options["SecurityOpt"])
            check(not options["PortBindings"] and options["PidsLimit"]==64 and options["Memory"]==192*1024*1024)
            check(options["LogConfig"]["Type"]=="none")
            networks=value["NetworkSettings"]["Networks"]
            check(set(networks)==({"investalo-local_demo_acceptance"} if service=="demo-acceptance-node"
                                  else {"investalo-local_demo_acceptance","investalo-local_database"}))
            for network in networks:
                check(json.loads(subprocess.check_output(["docker","network","inspect",network],timeout=5))[0]["Internal"] is True)
            files={item["Destination"] for item in value["Mounts"]}
            if service in ("demo-acceptance-node","demo-acceptance-api","demo-acceptance-disabled-api","demo-acceptance-audit"):
                check("/run/secrets/credentials_test_password_a" not in files)
            if service=="demo-acceptance-node":
                check(all(item["RW"] is False for item in value["Mounts"] if item["Type"]=="bind"))
            if service=="demo-acceptance-executor":
                check("/run/secrets/platform_migration_password" not in files
                      and "/run/secrets/platform_runtime_password" not in files)
                check(all(item["RW"] is False for item in value["Mounts"] if item["Type"]=="bind"))

    def stop(process):
        name=next(name for own,name,_ in owned if own is process)
        subprocess.run(["docker","stop","--time","3",name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                       timeout=10,check=False)
        process.wait(timeout=10)

    try:
        api=start("demo-acceptance-api")
        disabled=start("demo-acceptance-disabled-api")
        audit=start("demo-acceptance-audit",rpc=True)
        initial=read(audit)
        check(initial["kind"]=="configuration")
        run=initial.pop("run")
        executor=start("demo-acceptance-executor",run)
        send(audit,{"kind":"ready"})
        check(read(audit)["kind"]=="ready" and executor.poll()is None)
        node=start("demo-acceptance-node",run,rpc=True)
        send(node,initial)
        while True:
            message=read(node)
            if message["kind"]=="complete":
                inspect_owned()
                send(audit,{"kind":"complete"})
                final=read(audit)
                check(final["kind"]=="complete" and final["run"]==run)
                for process in (node,audit):
                    process.stdin.close()
                    check(process.wait(timeout=10)==0)
                check(api.poll()is None and disabled.poll()is None and executor.poll()is None)
                for process in (executor,api,disabled):
                    stop(process)
                packet=dict(schema="investalo-demo-local-acceptance/1",run=run,
                    checks=message["checks"]+final["checks"]+CHECKS,node_checks=message["checks"],audit_checks=final["checks"],
                    phases=["register","executor_restart","revoke","post_commit_unknown"],
                    actual=["HTTPS","BFF-P256","API","PostgreSQL015/016/017","AEAD","restricted-Python-mTLS-executor"],
                    synthetic=["session","broker-key-UID-parent-IP-provenance"],public_runtime_enabled=False,
                    host_checks=CHECKS)
                packet_directory=ROOT/"infra/local/bitget-demo-local-acceptance"/run
                packet_directory.mkdir(parents=True,mode=0o700)
                os.chmod(packet_directory.parent,0o700)
                descriptor=os.open(packet_directory/"receipt.json",os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(descriptor,"w")as output:
                    json.dump(packet,output,indent=2); output.write("\n")
                    output.flush(); os.fsync(output.fileno())
                if json.loads((packet_directory/"receipt.json").read_bytes())!=packet:
                    raise Failure()
                held=os.open(packet_directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
                try:
                    os.fsync(held)
                finally:
                    os.close(held)
                print(f"PASS: {packet['checks']} actual isolated Demo HTTPS/BFF/API/PG/AEAD/restricted-executor checks; synthetic session/provenance; run {run}")
                return
            if message["kind"]=="restart":
                stop(executor)
                executor=start("demo-acceptance-executor",run)
                send(audit,{"kind":"ready"})
                check(read(audit)["kind"]=="ready")
                send(node,{"kind":"restarted"})
            else:
                check(message["kind"]=="audit")
                send(audit,message)
                send(node,read(audit))
    finally:
        # Close audit input gracefully so its CAS binding restoration runs even
        # when another fixture process fails. Never kill it before this chance.
        for process,_,service in owned:
            if service=="demo-acceptance-audit" and process.poll()is None:
                try:
                    send(process,{"kind":"abort"})
                    process.stdin.close()
                    process.wait(timeout=15)
                except (OSError,subprocess.TimeoutExpired):
                    pass
        selector.close()
        for process,name,_ in reversed(owned):
            if process.poll()is None:
                try:
                    subprocess.run(["docker","stop","--time","3",name],stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,timeout=10,check=False)
                    process.wait(timeout=10)
                except (OSError,subprocess.TimeoutExpired):
                    process.kill()


if __name__=="__main__":
    try:
        if sys.argv[1:]==["--child"]:
            child()
        elif sys.argv[1:]==["--orchestrate"]:
            with exclusive_fixture():
                orchestrate()
        else:
            raise Failure()
    except Exception as error:
        if sys.argv[1:]==["--child"]:
            # Class names only, never exception text/SQL/parameters.
            code=type(error).__name__
            if code not in {"Failure","TypeError","KeyError","AttributeError","OnboardingRejected",
                            "DemoSecretRejected","EnvelopeRejected","UndefinedColumn","UndefinedTable",
                            "OperationalError","TimeoutError","SSLCertVerificationError"}:
                code="other"
            emit(dict(kind="failed",stage=STAGE,code=code))
        else:
            print("Demo local acceptance rejected; sensitive diagnostics suppressed.",file=sys.stderr)
        raise SystemExit(1) from None
