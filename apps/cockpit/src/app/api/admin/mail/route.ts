import { handleAdminMail } from "@/lib/admin-mail-server";
export const runtime = "nodejs";
export async function POST(request: Request) { return handleAdminMail(request); }
