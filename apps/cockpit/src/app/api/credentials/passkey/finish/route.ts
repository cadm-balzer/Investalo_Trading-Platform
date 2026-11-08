import { handleCredentialBrowserRequest } from "@/lib/passkey-credential-browser-server";

export async function POST(request: Request) {
  return handleCredentialBrowserRequest(request, "finish");
}
