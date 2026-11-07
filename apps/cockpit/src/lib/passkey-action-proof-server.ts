import "server-only";
import { randomUUID } from "node:crypto";
import { getBoundSession, type Session } from "./auth.ts";
import { apiRequest } from "./backend.ts";
import { getConfig } from "./config.ts";
import { randomToken } from "./security.ts";
import type { CredentialAction } from "./credential-action-contracts.ts";
import {
  beginPasskeyActionProof, finishPasskeyActionProof,
  readPasskeyActionGrant, confirmPasskeyActionProof,
  type PasskeyActionPorts,
} from "./passkey-action-proof.ts";

/** Prepared server adapter. No browser route or credential executor calls it yet. */
const ports: PasskeyActionPorts = {
  async current() {
    const config = await getConfig();
    const bound = await getBoundSession();
    if (!bound) throw new Error("PASSKEY_ACTION_REJECTED");
    return { ...bound, origin: config.origin };
  },
  async context(session: Session) {
    return apiRequest<unknown>(session, "/v1/passkeys/context", {}, await getConfig());
  },
  async metadata(session: Session, accountId: string) {
    return apiRequest<unknown>(session, `/v1/credential-actions/${accountId}`, {}, await getConfig());
  },
  async request(session: Session, path: string, body: Record<string, unknown>) {
    // All calls retain the actual OIDC issuer, subject and authentication time.
    return apiRequest<unknown>(session, path, {
      method: "POST", body: JSON.stringify(body),
    }, await getConfig());
  },
  now: () => Math.floor(Date.now() / 1000),
  randomToken,
  randomUuid: randomUUID,
};

export function prepareCredentialPasskeyProof(accountId: string, action: CredentialAction) {
  return beginPasskeyActionProof(ports, accountId, action);
}
export function verifyCredentialPasskeyProof(attemptId: string, response: unknown, confirmationToken: string) {
  return finishPasskeyActionProof(ports, attemptId, response, confirmationToken);
}
export function readCredentialPasskeyProof(grantId: string, confirmationToken: string) {
  return readPasskeyActionGrant(ports, grantId, confirmationToken);
}
export function confirmCredentialPasskeyProof(grantId: string, confirmationToken: string) {
  return confirmPasskeyActionProof(ports, grantId, confirmationToken);
}
