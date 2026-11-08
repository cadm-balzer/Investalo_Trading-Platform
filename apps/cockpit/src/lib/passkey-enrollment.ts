import "server-only";
import { getBoundSession, type Session } from "./auth.ts";
import { apiRequest } from "./backend.ts";
import { getConfig, type Config } from "./config.ts";
import { EncryptedStore } from "./store.ts";
import { randomToken } from "./security.ts";
import { assertAuthorizedSession, snapshotAuthorizedSession } from "./authorized-session.ts";
import {
  parsePasskeyContext, type PasskeyContext,
} from "./passkey-enrollment-state.ts";
import { beginEnrollmentFlow, finishEnrollmentFlow, type EnrollmentFlowPorts } from "./passkey-enrollment-flow.ts";

function ports(config: Config, expectedSession?: Readonly<Session>): EnrollmentFlowPorts {
  const authorized = expectedSession ? snapshotAuthorizedSession(expectedSession) : undefined;
  const store = new EncryptedStore(`${config.stateDir}/passkey-enrollment`, config.sessionSecret);
  return {
    async current() {
      const settings = await getConfig(), bound = await getBoundSession();
      if (authorized && bound) assertAuthorizedSession(authorized, bound.session);
      return bound ? { ...bound, origin: settings.origin } : null;
    },
    context: session => apiRequest<unknown>(session, "/v1/passkeys/context", {}, config),
    request: (session, path, body) => apiRequest<unknown>(session, path,
      { method: "POST", body: JSON.stringify(body) }, config),
    attempts: {
      put: (id, attempt) => store.put(id, attempt),
      get: id => store.get(id),
      consume: id => store.consume(id),
    },
    now: () => Math.floor(Date.now() / 1000),
    randomToken,
  };
}
export async function getPasskeyContext(session: Session, config = getConfig()): Promise<PasskeyContext> {
  const settings = await config;
  const value = await apiRequest<unknown>(session, "/v1/passkeys/context", {}, settings);
  return parsePasskeyContext(value, { tenantId: session.tenantId, authEpoch: session.authEpoch,
    rpId: new URL(settings.origin).hostname });
}
/** Invitation claim commits in the API before any browser or crypto work. */
export async function beginPasskeyEnrollment(ticket: unknown, expectedSession?: Session) {
  const authorized = expectedSession ? snapshotAuthorizedSession(expectedSession) : undefined;
  return beginEnrollmentFlow(ports(await getConfig(), authorized), ticket);
}
export async function finishPasskeyEnrollment(id: unknown, response: unknown, expectedSession?: Session): Promise<void> {
  const authorized = expectedSession ? snapshotAuthorizedSession(expectedSession) : undefined;
  return finishEnrollmentFlow(ports(await getConfig(), authorized), id, response);
}
