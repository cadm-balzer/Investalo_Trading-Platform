import "server-only";

/** Explicit local/check opt-in; never implies credential execution approval. */
export function passkeyProofPreviewEnabled(): boolean {
  return process.env.COCKPIT_PASSKEY_PROOF_PREVIEW === "1";
}
