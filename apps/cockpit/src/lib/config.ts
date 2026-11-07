import { readFile } from "node:fs/promises";

export type Config = {
  origin: string; issuer: string; clientId: string; clientSecret: string;
  sessionSecret: string; internalSecret: string; apiBase: string; stateDir: string;
};

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) throw new Error("CONFIG_UNAVAILABLE");
  return value;
}

function httpsOrigin(name: string): string {
  const url = new URL(required(name));
  if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash || url.pathname !== "/") {
    throw new Error("CONFIG_UNAVAILABLE");
  }
  return url.origin;
}

async function secret(name: string, minimum: number): Promise<string> {
  const value = (await readFile(required(name), "utf8")).trim();
  if (Buffer.byteLength(value) < minimum) throw new Error("CONFIG_UNAVAILABLE");
  return value;
}

export async function getConfig(): Promise<Config> {
  return {
    origin: httpsOrigin("COCKPIT_ORIGIN"),
    issuer: httpsOrigin("OIDC_ISSUER"),
    apiBase: httpsOrigin("API_BASE_URL"),
    clientId: required("OIDC_CLIENT_ID"),
    clientSecret: await secret("OIDC_CLIENT_SECRET_FILE", 32),
    sessionSecret: await secret("COCKPIT_SESSION_SECRET_FILE", 32),
    internalSecret: await secret("BFF_INTERNAL_AUTH_SECRET_FILE", 32),
    stateDir: required("COCKPIT_STATE_DIR"),
  };
}
