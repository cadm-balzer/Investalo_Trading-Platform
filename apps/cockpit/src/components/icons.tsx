type IconName = "overview" | "portfolio" | "journal" | "backtest" | "shield" | "arrow" | "exit" | "globe";
const paths: Record<IconName, string> = {
  overview: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  portfolio: "M3 8h18v13H3z M8 8V4h8v4 M3 13h18 M10 13v3h4v-3",
  journal: "M6 3h14v18H6a3 3 0 0 1 0-6h14 M6 3a3 3 0 0 0-3 3v12 M9 7h7 M9 11h5",
  backtest: "M3 21V3 M3 21h18 M7 16l4-5 4 2 6-9",
  shield: "M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6z M8 12l3 3 5-6",
  arrow: "M5 12h14 M13 6l6 6-6 6",
  exit: "M10 3H4v18h6 M10 12h11 M16 7l5 5-5 5",
  globe: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M3 12h18 M12 3c5 5 5 13 0 18 M12 3c-5 5-5 13 0 18",
};
export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}
export function Brand() {
  return <span className="brand"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>investalo<span className="brand-dot">.</span></span>;
}
