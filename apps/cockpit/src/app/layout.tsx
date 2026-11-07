import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Investalo Cockpit", template: "%s · Investalo" },
  description: "Dein privates Cockpit für Portfolio, Paper Trading und überprüfbare Strategien.",
  robots: { index: false, follow: false },
  icons: { icon: "/favicon.svg" },
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="de"><body>{children}</body></html>;
}
