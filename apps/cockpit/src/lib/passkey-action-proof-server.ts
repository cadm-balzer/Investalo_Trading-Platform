import "server-only";
import { randomUUID } from "node:crypto";
import { getBoundSession, type Session } from "./auth.ts";
import { apiRequest } from "./backend.ts";
import { getConfig } from "./config.ts";
import { randomToken } from "./security.ts";
import { assertAuthorizedSession, snapshotAuthorizedSession } from "./authorized-session.ts";
import type { CredentialAction } from "./credential-action-contracts.ts";
import {
  beginPasskeyActionProof, finishPasskeyActionProof,
  readPasskeyActionGrant, confirmPasskeyActionProof,
  type PasskeyActionPorts,
} from "./passkey-action-proof.ts";

/** Opt-in proof-only browser adapter. Credential execution remains disabled. */
function ports(expectedSession?: Session): PasskeyActionPorts {
  const expected = expectedSession ? snapshotAuthorizedSession(expectedSession) : undefined;
  return {
    async current() {
      const config = await getConfig();
      const bound = await getBoundSession();
      if (!bound) throw new Error("PASSKEY_ACTION_REJECTED");
      if (expected) assertAuthorizedSession(expected, bound.session);
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
}

export function prepareCredentialPasskeyProof(accountId: string, action: CredentialAction, expectedSession?: Session) {
  return beginPasskeyActionProof(ports(expectedSession), accountId, action);
}
export function verifyCredentialPasskeyProof(attemptId: string, response: unknown, confirmationToken: string, expectedSession?: Session) {
  return finishPasskeyActionProof(ports(expectedSession), attemptId, response, confirmationToken);
}
export function readCredentialPasskeyProof(grantId: string, confirmationToken: string, expectedSession?: Session) {
  return readPasskeyActionGrant(ports(expectedSession), grantId, confirmationToken);
}
export function confirmCredentialPasskeyProof(grantId: string, confirmationToken: string, expectedSession?: Session) {
  return confirmPasskeyActionProof(ports(expectedSession), grantId, confirmationToken);
}
