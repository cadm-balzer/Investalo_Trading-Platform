import "server-only";
import { getConfig, type Config } from "./config.ts";
import { internalToken, type Principal } from "./internal-token.ts";
import { limitedBody } from "./security.ts";

export type Membership = { tenant_id: string; tenant_name: string; role: string };
export type { Account, Position, JournalEntry, Job, Overview } from "./contracts.ts";

export class BackendError extends Error {
  constructor(public status: number) { super("BACKEND_UNAVAILABLE"); }
}

export async function apiRequest<T>(principal: Principal, path: string, options: { method?: string; body?: string; idempotencyKey?: string } = {}, suppliedConfig?: Config): Promise<T> {
  const config = suppliedConfig ?? await getConfig();
  const method = options.method ?? "GET", body = options.body ?? "";
  const jwt = await internalToken(config.internalSecret, principal, method, path, body);
  const response = await fetch(`${config.apiBase}${path}`, {
    method, cache: "no-store", redirect: "error", signal: AbortSignal.timeout(5000),
    headers: {
      Authorization: `Bearer ${jwt}`, "Content-Type": "application/json",
      ...(options.idempotencyKey ? { "Idempotency-Key": options.idempotencyKey } : {}),
    },
    ...(body ? { body } : {}),
  });
  if (!response.ok) throw new BackendError(response.status);
  // Bound bytes before JSON parsing; a remote result cannot exhaust the BFF
  // while waiting for field/curve validation.
  const raw = await limitedBody(new Request("https://response.invalid", {
    method: "POST", body: response.body, duplex: "half",
    headers: response.headers.get("content-length") ? { "content-length": response.headers.get("content-length")! } : {},
  } as RequestInit), 2 * 1024 * 1024);
  return JSON.parse(raw) as T;
}
