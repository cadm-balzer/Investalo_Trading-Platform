import test from "node:test";
import assert from "node:assert/strict";
import dns from "node:dns/promises";
import tls from "node:tls";
import type { AddressInfo } from "node:net";
import { sendEmailCode, publicSmtpAddress } from "../src/lib/admin-smtp.ts";
import { SYNTHETIC_DEMO_TLS } from "./helpers/demo-private-tls-material.ts";

test("SMTP blocks private, loopback, metadata, documentation and multicast addresses", () => {
  for (const ip of ["127.0.0.1","10.1.2.3","172.16.0.1","169.254.169.254","192.168.1.1",
    "100.64.0.1","192.0.2.1","198.18.0.1","203.0.113.1","224.1.1.1","255.255.255.255"])
    assert.equal(publicSmtpAddress(ip), false, ip);
  assert.equal(publicSmtpAddress("93.184.216.34"), true);
});

test("actual TLS SMTP authenticates once and acknowledges DATA without logging private replies", async t => {
  const received: string[] = [];
  const server = tls.createServer({ cert: SYNTHETIC_DEMO_TLS.serverCertificate,
    key: SYNTHETIC_DEMO_TLS.serverPrivateKey }, socket => {
    socket.setEncoding("utf8"); socket.write("220 fixture ready\r\n");
    let buffer = "", body = false;
    socket.on("data", (bytes: string) => {
      buffer += bytes;
      while (buffer.includes("\r\n")) {
        const end = buffer.indexOf("\r\n"), line = buffer.slice(0,end);
        buffer = buffer.slice(end+2); received.push(line);
        if (body) { if (line === ".") { body=false; socket.write("250 message accepted\r\n"); } continue; }
        if (line.startsWith("EHLO")) socket.write("250-fixture\r\n250 AUTH PLAIN LOGIN\r\n");
        else if (line.startsWith("AUTH PLAIN")) socket.write("235 authenticated\r\n");
        else if (line.startsWith("MAIL FROM") || line.startsWith("RCPT TO")) socket.write("250 accepted\r\n");
        else if (line === "DATA") { body=true; socket.write("354 send body\r\n"); }
        else if (line === "QUIT") socket.end("221 bye\r\n");
      }
    });
    socket.on("error", () => {});
  });
  await new Promise<void>(resolve => server.listen(0,"127.0.0.1",resolve));
  t.after(() => new Promise<void>(resolve => server.close(() => resolve())));
  const original = tls.connect, address=server.address() as AddressInfo;
  t.mock.method(dns,"lookup",async () => [{address:"93.184.216.34",family:4}]);
  t.mock.method(tls,"connect",(options: tls.ConnectionOptions) => {
    assert.equal(options.host,"93.184.216.34");
    assert.equal(options.servername,"executor.fixture.invalid");
    assert.equal(options.rejectUnauthorized,true);
    return original({ ...options, host:"127.0.0.1",port:address.port,ca:SYNTHETIC_DEMO_TLS.ca });
  });
  await sendEmailCode({host:"executor.fixture.invalid",port:465,username:"synthetic-user",
    password:"synthetic-secret",sender:"sender@fixture.invalid"},"owner@fixture.invalid","12345678");
  assert.equal(received.filter(line=>line.startsWith("AUTH PLAIN")).length,1);
  assert.ok(received.includes("Dein Bestaetigungscode: 12345678"));
  assert.ok(received.includes("RCPT TO:<owner@fixture.invalid>"));
});

test("DNS rejection occurs before any socket or credential send", async t => {
  t.mock.method(dns,"lookup",async()=>[{address:"127.0.0.1",family:4}]);
  let connected=false;
  t.mock.method(tls,"connect",()=>{connected=true;throw new Error();});
  await assert.rejects(sendEmailCode({host:"mail.fixture.invalid",port:465,username:"user",password:"secret",
    sender:"sender@fixture.invalid"},"owner@fixture.invalid","12345678"),/ADMIN_MAIL_UNAVAILABLE/);
  assert.equal(connected,false);
});
