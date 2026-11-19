/** Bounded implicit-TLS SMTP submission. No plaintext, redirects or retries. */
import dns from "node:dns/promises";
import { BlockList } from "node:net";
import tls, { type TLSSocket } from "node:tls";
import { randomUUID } from "node:crypto";
import { mailAddress, mailHost, mailFailure, type MailSettings } from "./admin-mail-state.ts";

const blocked = new BlockList();
for (const [address, prefix] of [
  ["0.0.0.0",8],["10.0.0.0",8],["100.64.0.0",10],["127.0.0.0",8],["169.254.0.0",16],
  ["172.16.0.0",12],["192.0.0.0",24],["192.0.2.0",24],["192.168.0.0",16],
  ["192.88.99.0",24],["198.18.0.0",15],["198.51.100.0",24],["203.0.113.0",24],
  ["224.0.0.0",4],["240.0.0.0",4],
] as const) blocked.addSubnet(address, prefix, "ipv4");
export function publicSmtpAddress(address: string) { return !blocked.check(address, "ipv4"); }

class Replies {
  #socket: TLSSocket; #buffer = ""; #lines: string[] = [];
  #waiting: { resolve(value: string[]): void; reject(error: Error): void } | null = null;
  #failed = false; #code: string | null = null; #bytes = 0;
  constructor(socket: TLSSocket) {
    this.#socket = socket;
    socket.setEncoding("utf8");
    socket.on("data", (data: string) => {
      try {
        this.#bytes += Buffer.byteLength(data);
        this.#buffer += data;
        if (this.#buffer.length > 8192 || this.#bytes > 65536) throw mailFailure();
        while (this.#buffer.includes("\r\n")) {
          const at = this.#buffer.indexOf("\r\n"), line = this.#buffer.slice(0, at);
          this.#buffer = this.#buffer.slice(at + 2);
          if (!/^[0-9]{3}[ -][\x20-\x7e]*$/.test(line) || line.length > 2048 || this.#lines.length >= 32) throw mailFailure();
          if (this.#code !== null && this.#code !== line.slice(0, 3)) throw mailFailure();
          this.#code = line.slice(0, 3); this.#lines.push(line);
          if (line[3] === " ") {
            if (!this.#waiting) throw mailFailure();
            const pending = this.#waiting, lines = this.#lines;
            this.#waiting = null; this.#lines = []; this.#code = null;
            pending.resolve(lines);
          }
        }
      } catch { this.fail(); }
    });
    socket.on("error", () => this.fail());
    socket.on("end", () => this.fail());
    socket.on("close", () => this.fail());
  }
  fail() {
    this.#failed = true;
    this.#waiting?.reject(mailFailure()); this.#waiting = null;
    this.#socket.destroy();
  }
  read(): Promise<string[]> {
    if (this.#failed || this.#waiting) return Promise.reject(mailFailure());
    return new Promise((resolve, reject) => { this.#waiting = { resolve, reject }; });
  }
}
async function reply(pending: Promise<string[]>, code: number) {
  const lines = await pending;
  if (lines.at(-1)?.slice(0, 3) !== String(code)) throw mailFailure();
  return lines;
}

async function submit(settings: MailSettings, recipient: string, subject: string, lines: string[]) {
  let socket: TLSSocket | undefined, deadline: ReturnType<typeof setTimeout> | undefined;
  try {
    const host = mailHost(settings.host), to = mailAddress(recipient), from = mailAddress(settings.sender);
    if (settings.port !== 465) throw mailFailure();
    const addresses = await Promise.race([
      dns.lookup(host, { family: 4, all: true }),
      new Promise<never>((_, reject) => { deadline = setTimeout(() => reject(mailFailure()), 5000); }),
    ]);
    clearTimeout(deadline);
    if (!addresses.length || addresses.some(v => v.family !== 4 || !publicSmtpAddress(v.address))) throw mailFailure();
    // Connect to the resolved public IP. Certificate/SNI still bind the original
    // configured hostname, so a second DNS lookup cannot redirect credentials.
    socket = tls.connect({ host: addresses[0].address, port: 465, servername: host,
      rejectUnauthorized: true, minVersion: "TLSv1.2" });
    const replies = new Replies(socket), greeting = reply(replies.read(), 220);
    deadline = setTimeout(() => replies.fail(), 20_000);
    const secure = new Promise<void>((resolve, reject) => {
      socket!.once("secureConnect", () => socket!.authorized ? resolve() : reject(mailFailure()));
      socket!.once("error", () => reject(mailFailure()));
    });
    await Promise.all([secure, greeting]);
    async function command(wire: string, expected: number) {
      const response = reply(replies.read(), expected);
      socket!.write(wire + "\r\n");
      return response;
    }
    const hello = await command("EHLO cockpit.investalo.de", 250);
    const auth = hello.map(line => line.slice(4)).find(line => /^AUTH[ =]/.test(line));
    if (!auth) throw mailFailure();
    if (/\bPLAIN\b/.test(auth)) {
      await command("AUTH PLAIN " + Buffer.from(`\0${settings.username}\0${settings.password}`).toString("base64"), 235);
    } else if (/\bLOGIN\b/.test(auth)) {
      await command("AUTH LOGIN", 334);
      await command(Buffer.from(settings.username).toString("base64"), 334);
      await command(Buffer.from(settings.password).toString("base64"), 235);
    } else throw mailFailure();
    await command(`MAIL FROM:<${from}>`, 250);
    await command(`RCPT TO:<${to}>`, 250);
    await command("DATA", 354);
    const body = [
      `From: ${from}`, `To: ${to}`, `Subject: ${subject}`,
      `Date: ${new Date().toUTCString()}`, `Message-ID: <${randomUUID()}@cockpit.investalo.de>`,
      "MIME-Version: 1.0", "Content-Type: text/plain; charset=utf-8", "Content-Transfer-Encoding: 7bit", "",
      ...lines,
    ].join("\r\n");
    await command(body + "\r\n.", 250);
    // DATA250 is the acknowledged handoff. Losing QUIT must not resend.
    socket.end("QUIT\r\n");
  } catch { throw mailFailure(); }
  finally { if (deadline) clearTimeout(deadline); socket?.destroy(); }
}

export async function sendEmailCode(settings: MailSettings, recipient: string, code: string) {
  if (!/^[0-9]{8}$/.test(code)) throw mailFailure();
  return submit(settings, recipient, "Investalo - E-Mail bestaetigen", [
    `Dein Bestaetigungscode: ${code}`, "", "Der Code gilt 10 Minuten.",
    "Gib ihn im angemeldeten Cockpit unter Administration > E-Mail ein.",
    "https://cockpit.investalo.de/admin/settings", "",
    "Wenn du diese Bestaetigung nicht angefordert hast, ignoriere diese Nachricht.", "",
  ]);
}

/** Operator-only delivery after verified mail and actual DB ticket issuance. */
export async function sendPasskeyTicket(settings: MailSettings, recipient: string, token: string) {
  if (!/^[A-Za-z0-9_-]{43}$/.test(token)) throw mailFailure();
  return submit(settings, recipient, "Investalo - Passkey registrieren", [
    "Dein einmaliges Passkey-Registrierungsticket:", token, "", "Das Ticket gilt hoechstens 10 Minuten.",
    "Gib es im angemeldeten Cockpit hier ein: https://cockpit.investalo.de/security/passkeys",
    "Bestaetige danach den Passkey mit PIN oder Biometrie deines Geraets.", "",
    "Wenn du diese Registrierung nicht angefordert hast, ignoriere diese Nachricht.", "",
  ]);
}
