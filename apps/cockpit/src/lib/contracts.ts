export type Account = { id: string; name: string; mode: string; currency: string; equity?: string; cash?: string; updated_at?: string | null };
export type Position = { account_id: string; symbol: string; quantity: string; average_price: string; observed_at?: string; unrealized_pnl?: string; stage?: number };
export type JournalEntry = { id: string; created_at: string; event_type: string; message?: string; symbol?: string | null };
export type Job = { id: string; status: string; kind?: string; created_at: string; symbol?: string; payload?: { symbol?: string; timeframe?: string }; error?: string | null };
export type Overview = { mode: "paper"; live_enabled: false; tenant_id: string; accounts: Account[]; positions: Position[]; journal: JournalEntry[]; jobs: Job[] };

/** Validate before publishing any tenant data into a response or component. */
export function parseOverview(value: unknown, tenantId: string): Overview {
  if (!value || typeof value !== "object") throw new Error("OVERVIEW_REJECTED");
  const candidate = value as Overview;
  if (candidate.mode !== "paper" || candidate.live_enabled !== false || candidate.tenant_id !== tenantId ||
    ![candidate.accounts, candidate.positions, candidate.journal, candidate.jobs].every(Array.isArray)) throw new Error("OVERVIEW_REJECTED");
  return candidate;
}
