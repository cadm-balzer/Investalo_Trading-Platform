/** Emits public synthetic test data to the offline Python interoperability check. */
import {
  createPasskeyCredentialActionToken, type PasskeyCredentialAuthorization,
  type PasskeyCredentialTokenInput,
} from "../../src/lib/passkey-credential-token.ts";
import { createCredentialActionToken } from "../../src/lib/credential-action-token.ts";
import { hash, now, signing } from "./passkey-credential-fixture.ts";

const samples: { name: string; input: PasskeyCredentialTokenInput }[] = [];
for (const action of ["register", "replace", "revoke"] as const) {
  samples.push({ name: action, input: signing(action) });
}
const whitespace = signing("replace"), whitespaceBody = " \n" + whitespace.body + "\t";
samples.push({ name: "unchanged-whitespace-and-UTF8", input: { ...whitespace, body: whitespaceBody,
  authorization: { ...(whitespace.authorization as PasskeyCredentialAuthorization), body_sha256: hash(whitespaceBody) } } });
const short = signing("revoke");
samples.push({ name: "short-original-session", input: { ...short,
  context: { ...short.context, sessionExpiresAt: now + 4 },
  authorization: { ...(short.authorization as PasskeyCredentialAuthorization),
    session_expires_at: now + 4, expires_at: now + 4 } } });
const maximum = signing("revoke"), maximumReceipt = maximum.authorization as PasskeyCredentialAuthorization,
  maximumTarget = { ...maximumReceipt.target, expected_revision: Number.MAX_SAFE_INTEGER,
    expected_storage: Number.MAX_SAFE_INTEGER - 1 };
const { action: _action, ...maximumRequest } = maximumTarget;
const maximumBody = JSON.stringify(maximumRequest);
samples.push({ name: "exact-safe-integer-boundary", input: { ...maximum, body: maximumBody,
  authorization: { ...maximumReceipt, target: maximumTarget, body_sha256: hash(maximumBody) } } });
const rows = [];
for (const { name, input } of samples) {
  const authorization = input.authorization as PasskeyCredentialAuthorization;
  rows.push({ name, action: authorization.target.action, context: input.context, authorization,
    body: input.body, token: await createPasskeyCredentialActionToken(input), now,
    legacy_token: await createCredentialActionToken({
      key: input.key, oidcIssuer: input.context.oidcIssuer,
      identity: { subject: input.context.subject, issuer: input.context.oidcIssuer,
        authTime: now - 1, amr: ["pwd", "mfa"] }, tenantId: input.context.tenantId,
      authEpoch: input.context.authEpoch, startedAt: now - 2,
      target: authorization.target, body: input.body, now,
    }),
  });
}
process.stdout.write(JSON.stringify(rows));
