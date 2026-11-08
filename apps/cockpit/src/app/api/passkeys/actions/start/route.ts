import { getSession } from "@/lib/auth";
import { getConfig } from "@/lib/config";
import { handlePasskeyProofHttp } from "@/lib/passkey-action-proof-http";
import { passkeyProofPreviewEnabled } from "@/lib/passkey-action-preview";
import { prepareCredentialPasskeyProof } from "@/lib/passkey-action-proof-server";

export async function POST(request: Request) {
  return handlePasskeyProofHttp(request, "start", {
    enabled: passkeyProofPreviewEnabled,
    origin: async () => (await getConfig()).origin,
    session: getSession,
    execute: (input, session) => prepareCredentialPasskeyProof(input.platform_account_id, input.action, session),
    now: () => Math.floor(Date.now() / 1000),
  });
}
