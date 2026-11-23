import test, { afterEach } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { createHmac } from "node:crypto";
import https from "node:https";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as contracts from "../src/lib/demo-market-order-contract.ts";
import * as account from "../src/lib/demo-account-contract.ts";
import * as authorized from "../src/lib/authorized-session.ts";
import * as uuid from "../src/lib/credential-action-contracts.ts";
import * as metadata from "../src/lib/demo-trading-credential-action-contracts.ts";
import * as consent from "../src/lib/demo-btc-order-consent.ts";
import * as objects from "../src/lib/passkey-enrollment-state.ts";
import * as security from "../src/lib/security.ts";
import * as proof from "../src/lib/demo-trading-passkey-action-proof-state.ts";
import { marketReadPacket } from "../src/lib/demo-market-order-executor.ts";
import { demoTlsFixture } from "./helpers/demo-trading-private-identity-fixture.ts";
import { SYNTHETIC_DEMO_TLS } from "./helpers/demo-private-tls-material.ts";
const id = (n: number) => `00000000-0000-0000-0000-${String(n).padStart(12,"0")}`;
const ORIGIN = "https://cockpit.investalo.de";
const require = createRequire(import.meta.url), originalFlag = process.env.COCKPIT_DEMO_BTC_MARKET_TEST;
afterEach(() => { if (originalFlag === undefined) delete process.env.COCKPIT_DEMO_BTC_MARKET_TEST;
  else process.env.COCKPIT_DEMO_BTC_MARKET_TEST=originalFlag; });
function load(path: string, inject: Record<string, unknown>) {
  const wire=ts.transpileModule(readFileSync(new URL(path,import.meta.url),"utf8"),
    {compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  const module={exports:{} as any};
  new Function("require","module","exports",wire)((key:string)=>Object.hasOwn(inject,key)?inject[key]:require(key),module,module.exports);
  return module.exports;
}
function status(): contracts.MarketStatus {
  return {schema:"investalo-demo-market-status/1",command_id:id(6),state:"filled",requested_quantity_btc:"0.0003",
    filled_quantity_btc:"0.0003",average_price_usdt:"70000",reported_fee_usdt:null,observed_ms:Date.now(),
    position_matched:true,order_resubmit_allowed:false};
}
function fixture() {
  process.env.COCKPIT_DEMO_BTC_MARKET_TEST="1";
  const now=Math.floor(Date.now()/1000);
  const session={issuer:"https://auth.cockpit.investalo.de",subject:"synthetic-market-owner",
    oidcAuthTime:now-3600,tenantId:id(1),authEpoch:3,expiresAt:now+3600,
    displayName:"Synthetic",tenantName:"Synthetic",csrf:Buffer.alloc(32,1).toString("base64url")};
  const original={handle:Buffer.alloc(32,2).toString("base64url"),session};
  const f={current:original as typeof original|null,calls:0,role:"owner",mutate:()=>{}};
  const m=()=>({tenant_id:id(1),auth_epoch:3,purpose:"demo_futures_spot_trading",profile:"bitget-classic-demo-trading-secret/1",
    environment:"demo",account:{id:id(4),name:"Demo",broker:"bitget",mode:"bitget_demo",currency:"USDT",status:"ready"},
    connection:{connection_id:id(5),credential_revision:1,storage_version:1,status:"active"},key_authorities:["coow","cpow","stow"]});
  const server=load("../src/lib/demo-market-order-server.ts",{
    "server-only":{},"./auth.ts":{getBoundSession:async()=>f.current},
    "./backend.ts":{apiRequest:async(_s:unknown,path:string)=>path==="/v1/me"?{
      user:{id:id(2),subject:session.subject,auth_epoch:3},
      memberships:[{tenant_id:id(1),tenant_name:"Synthetic",role:f.role}],live_enabled:false}:m()},
    "./authorized-session.ts":authorized,"./credential-action-contracts.ts":uuid,"./demo-account-contract.ts":account,
    "./demo-trading-credential-action-contracts.ts":metadata,"./demo-btc-order-consent.ts":consent,
    "./demo-market-order-contract.ts":contracts,"./security.ts":security,
    "./demo-trading-passkey-credential-browser-server.ts":{runtime:async()=>({accountId:id(4),check:async()=>{},
      identity:{marketRead:async()=>{f.calls++;f.mutate();return status();},
        marketSubmit:async(request:Request,deps:any)=>{
          f.calls++;const packet=await consent.prepareDemoBTCMarketConsent(request,{
            ...deps,accountId:id(4),signingKey:new Uint8Array(32).fill(83)});
          assert.equal(packet.context.user_id,id(2));f.mutate();
          return {...status(),state:"acknowledged",filled_quantity_btc:null,average_price_usdt:null,position_matched:false};
        }}})}
  });
  const target={platform_account_id:id(4),connection_id:id(5),credential_revision:1,storage_version:1,
    command_id:id(6),intent_sha256:"a".repeat(64),confirmation:contracts.MARKET_CONFIRMATION,
    outbox_receipt:{schema:"bitget-classic-demo-outbox/1",outbox_id:id(9),binding_digest:"b".repeat(64),revision:1,
      head:"c".repeat(64),state_digest:"d".repeat(64)}};
  const request=(phase="observe",body:unknown={command_id:"latest"},headers:Record<string,string>={})=>
    new Request(ORIGIN+`/api/bitget-demo/orders/btc-market/${phase}`,{
      method:"POST",headers:{origin:ORIGIN,"sec-fetch-site":"same-origin","content-type":"application/json",
        "x-csrf-token":session.csrf,...headers},body:JSON.stringify(body)});
  return {f,original,server,target,request};
}
test("Market status preserves worse actual fill and unknown fee; bogus quantities and resend flags deny",()=>{
  const s=status();assert.deepEqual(contracts.parseMarketStatus(s,id(6)),s);
  for (const change of [{order_resubmit_allowed:true},{filled_quantity_btc:"0.0004"},{average_price_usdt:null},
    {command_id:id(9)},{native_order_id:"not-allowed"},{position_matched:1},{state:"acknowledged"}])
    assert.throws(()=>contracts.parseMarketStatus({...s,...change},id(6)));
});
test("Order routes default off and require the actual logged-in session before executor access",async()=>{
  const f=fixture();delete process.env.COCKPIT_DEMO_BTC_MARKET_TEST;
  assert.equal((await f.server.handleDemoMarketOrder(f.request(),"observe")).status,404);
  process.env.COCKPIT_DEMO_BTC_MARKET_TEST="1";f.f.current=null;
  assert.equal((await f.server.handleDemoMarketOrder(f.request(),"observe")).status,401);assert.equal(f.f.calls,0);
});
test("Origin CSRF cross-site and membership failures stop before executor",async()=>{
  const headers: Record<string,string>[] = [{origin:"https://foreign.invalid"},{"x-csrf-token":"foreign"},{"sec-fetch-site":"cross-site"}];
  for (const header of headers) {
    const f=fixture();assert.equal((await f.server.handleDemoMarketOrder(f.request("observe",undefined,header),"observe")).status,503);
    assert.equal(f.f.calls,0);
  }
  const f=fixture();f.f.role="viewer";
  assert.equal((await f.server.handleDemoMarketOrder(f.request(),"observe")).status,503);assert.equal(f.f.calls,0);
});
test("Submit sends the own exact consent packet and publishes ACK without invented fills",async()=>{
  const f=fixture(),response=await f.server.handleDemoMarketOrder(f.request("submit",f.target),"submit");
  assert.equal(response.status,200);const body=await response.json();
  assert.equal(body.state,"acknowledged");assert.equal(body.filled_quantity_btc,null);
  assert.doesNotMatch(JSON.stringify(body),/Bearer|session_binding|body_sha256/);
});
test("Session replacement after executor returns discards the result and requests status only",async()=>{
  const f=fixture();f.f.mutate=()=>{f.f.current={...f.original,session:{...f.original.session,authEpoch:4}};};
  const response=await f.server.handleDemoMarketOrder(f.request("submit",f.target),"submit");
  assert.equal(response.status,503);assert.match((await response.json()).error,/Teststatus prüfen/);
});
test("Initial Market controls expose preparation and GET-only recovery; no auto-send or fill",()=>{
  const module=load("../src/components/demo-market-order.tsx",{"../lib/demo-market-order-contract":contracts});
  const html=renderToStaticMarkup(React.createElement(module.DemoMarketOrder,{tenantId:id(1),accountId:id(4),csrf:"synthetic"}));
  assert.match(html,/Demotest vorbereiten/);assert.match(html,/Teststatus prüfen/);
  assert.doesNotMatch(html,/Marketorder einmal senden|Vollständig ausgeführt/);
});
test("Actual mTLS observer carries independent context and own domain; wrong command never publishes",async t=>{
  const f=fixture(),now=Math.floor(Date.now()/1000), key=new Uint8Array(32).fill(83);
  const packet=marketReadPacket({phase:"observe",authorized:{...f.original,origin:ORIGIN},userId:id(2),
    target:{platform_account_id:id(4),connection_id:id(5),credential_revision:1,storage_version:1,command_id:id(6)},
    signingKey:key,now});
  let published=status(),calls=0;
  const native=await demoTlsFixture(t,(request,response)=>{
    calls++;assert.equal(request.url,"/v1/bitget-demo-trading/market-order-observe");
    const [a,b,c]=request.headers.authorization!.slice(7).split(".");
    assert.equal(c,createHmac("sha256",key).update(a+"."+b).digest("base64url"));
    assert.equal(JSON.parse(Buffer.from(b,"base64url").toString()).kind,"investalo-demo-btc-market-observe/1");
    const context=JSON.parse(Buffer.from(request.headers["x-investalo-credential-context"] as string,"base64url").toString());
    assert.equal(context.subject,f.original.session.subject);
    request.resume();request.on("end",()=>{const body=JSON.stringify(published);
      response.writeHead(200,{"Content-Type":"application/json","Content-Length":Buffer.byteLength(body)});response.end(body);});
  });
  const executor=load("../src/lib/demo-market-order-executor.ts",{
    "./demo-trading-passkey-action-proof-state.ts":proof,"./passkey-enrollment-state.ts":objects,
    "./demo-market-order-contract.ts":contracts,"node:https":{default:{request:(_uri:URL,options:any,callback:any)=>
      https.request(new URL(native.origin),options,callback)}}});
  const tls={ca:Buffer.from(SYNTHETIC_DEMO_TLS.ca),certificate:Buffer.from(SYNTHETIC_DEMO_TLS.clientCertificate),
    privateKey:Buffer.from(SYNTHETIC_DEMO_TLS.clientPrivateKey)};
  assert.deepEqual(await executor.sendMarketPacket("https://demo-trading-executor.cockpit.internal:9443",tls,"observe",packet),published);
  published={...status(),command_id:id(99)};
  await assert.rejects(executor.sendMarketPacket("https://demo-trading-executor.cockpit.internal:9443",tls,"observe",packet));
  assert.equal(calls,2);
});
