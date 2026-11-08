import { getSession } from "@/lib/auth";
import { getConfig } from "@/lib/config";
import { handlePasskeyProofHttp } from "@/lib/passkey-action-proof-http";
import { passkeyProofPreviewEnabled } from "@/lib/passkey-action-preview";
import { verifyCredentialPasskeyProof } from "@/lib/passkey-action-proof-server";

export async function POST(request: Request) {
  return handlePasskeyProofHttp(request, "finish", {
    enabled: passkeyProofPreviewEnabled,
    origin: async () => (await getConfig()).origin,
    session: getSession,
    execute: (input, session) => verifyCredentialPasskeyProof(input.attempt_id, input.credential, input.confirmation_token, session),
    now: () => Math.floor(Date.now() / 1000),
  });
}
