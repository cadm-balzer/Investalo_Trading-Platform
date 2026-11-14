"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export function FuturesAssetRefresh() {
  const router = useRouter();
  useEffect(() => {
    const refresh = () => { if (document.visibilityState === "visible") router.refresh(); };
    const timer = setInterval(refresh, 15_000);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [router]);
  return <small>Aktualisiert alle 15 Sekunden · Zeiten Europe/Berlin</small>;
}
