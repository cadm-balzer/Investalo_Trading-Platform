import { handleDemoCredentialBrowserRequest } from "@/lib/demo-passkey-credential-browser-server";

export async function POST(request: Request) {
  return handleDemoCredentialBrowserRequest(request, "finish");
}
