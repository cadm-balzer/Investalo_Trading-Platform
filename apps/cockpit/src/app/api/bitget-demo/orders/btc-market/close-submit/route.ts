import { handleDemoMarketOrder } from "@/lib/demo-market-order-server";
export const dynamic = "force-dynamic";
export async function POST(request: Request) { return handleDemoMarketOrder(request, "close-submit"); }
