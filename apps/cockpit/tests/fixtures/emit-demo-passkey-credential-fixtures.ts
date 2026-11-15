/** Public synthetic fixtures only; no stored purpose authority is fabricated. */
import { createDemoPasskeyCredentialActionToken,
  type DemoPasskeyCredentialAuthorization } from "../../src/lib/demo-passkey-credential-token.ts";
import { createPasskeyCredentialActionToken } from "../../src/lib/passkey-credential-token.ts";
import { hash, now, signing } from "./demo-passkey-credential-fixture.ts";

const samples = [signing("register"), signing("revoke")];
const whitespace = signing("register"), body = " \n" + whitespace.body + "\t";
samples.push({ ...whitespace, body, authorization: {
  ...whitespace.authorization as DemoPasskeyCredentialAuthorization, body_sha256: hash(body),
} });
const short = signing("revoke");
samples.push({ ...short, context: { ...short.context, sessionExpiresAt: now + 4 }, authorization: {
  ...short.authorization as DemoPasskeyCredentialAuthorization,
  session_expires_at: now + 4, expires_at: now + 4,
} });
const maximum = signing("revoke"), receipt = maximum.authorization as DemoPasskeyCredentialAuthorization;
const target = { ...receipt.target, expected_storage: Number.MAX_SAFE_INTEGER - 1 };
const { action: _action, ...request } = target;
const maximumBody = JSON.stringify(request);
samples.push({ ...maximum, body: maximumBody, authorization: {
  ...receipt, target, body_sha256: hash(maximumBody),
} });
const rows = [];
for (const input of samples) {
  const authorization = input.authorization as DemoPasskeyCredentialAuthorization;
  rows.push({ action: authorization.target.action, context: input.context, authorization, body: input.body, now,
    token: await createDemoPasskeyCredentialActionToken(input),
    normal_token: await createPasskeyCredentialActionToken({ ...input, authorization: {
      ...authorization, kind: "passkey-credential-authorization/1",
    } }),
  });
}
process.stdout.write(JSON.stringify(rows));
