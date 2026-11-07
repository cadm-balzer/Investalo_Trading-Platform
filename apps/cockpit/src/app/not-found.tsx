import Link from "next/link";
export default function NotFound() {
  return <main className="error-page"><span className="eyebrow">INVESTALO COCKPIT</span><h1>Hier gibt es noch keinen Kurs.</h1><p>Die angeforderte Seite wurde nicht gefunden.</p><Link className="button primary" href="/">Zur Übersicht</Link></main>;
}
