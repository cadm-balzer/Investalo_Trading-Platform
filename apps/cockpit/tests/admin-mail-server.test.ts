import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { randomBytes } from "node:crypto";
import ts from "typescript";
import { AdminMailStore } from "../src/lib/admin-mail-state.ts";
import * as authorized from "../src/lib/authorized-session.ts";
import * as codecs from "../src/lib/passkey-enrollment-state.ts";
import * as security from "../src/lib/security.ts";

const id=(n:number)=>`00000000-0000-0000-0000-${String(n).padStart(12,"0")}`;
async function fixture(t: test.TestContext) {
  const directory=await mkdtemp(join(tmpdir(),"investalo-admin-http-"));
  t.after(()=>rm(directory,{recursive:true,force:true}));
  const saved=process.env.COCKPIT_PLATFORM_ADMIN;
  process.env.COCKPIT_PLATFORM_ADMIN="1";
  const key=Symbol.for("investalo.platform-admin-mail/1");
  delete (globalThis as any)[key];
  t.after(()=>{delete (globalThis as any)[key]; if(saved===undefined)delete process.env.COCKPIT_PLATFORM_ADMIN;else process.env.COCKPIT_PLATFORM_ADMIN=saved;});
  const now=Math.floor(Date.now()/1000);
  const x={bound:{handle:security.randomToken(),session:{subject:"synthetic-admin",issuer:"https://auth.cockpit.investalo.de",
    tenantId:id(1),authEpoch:1,oidcAuthTime:now,expiresAt:now+1800,csrf:security.randomToken(),displayName:"Fixture",tenantName:"Fixture"}},
    role:"owner",user:id(2),calls:0};
  const authority={tenantId:id(1),userId:id(2),subject:"synthetic-admin",issuer:x.bound.session.issuer,
    origin:"https://cockpit.investalo.de",recipient:"owner@fixture.invalid",defaultHost:"mail.fixture.invalid",keySha256:"a".repeat(64)};
  const store=new AdminMailStore({directory:join(directory,"mail"),key:randomBytes(32),binding:"synthetic",
    recipient:authority.recipient,defaultHost:authority.defaultHost});
  const inject:Record<string,unknown>={
    "server-only":{},"./auth.ts":{getBoundSession:async()=>x.bound},
    "./config.ts":{getConfig:async()=>({origin:authority.origin,issuer:authority.issuer,stateDir:directory})},
    "./backend.ts":{apiRequest:async()=>{x.calls++;return {user:{id:x.user,subject:x.bound.session.subject,auth_epoch:1},
      memberships:[{tenant_id:id(1),tenant_name:"Fixture",role:x.role}],live_enabled:false};}},
    "./authorized-session.ts":authorized,"./passkey-enrollment-state.ts":codecs,"./security.ts":security,
    "./admin-mail-state.ts":{mailFailure:()=>new Error("ADMIN_MAIL_UNAVAILABLE")},
    "./admin-mail-authority.ts":{loadMailAuthority:async()=>({authority,digest:"fixture",key:randomBytes(32)}),mailStore:()=>store},
    "./admin-smtp.ts":{sendEmailCode:async()=>{throw new Error("Unexpected SMTP");}},
  };
  const code=ts.transpileModule(readFileSync(new URL("../src/lib/admin-mail-server.ts",import.meta.url),"utf8"),
    {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
  const module={exports:{} as any};
  new Function("require","module","exports",code)((name:string)=>{assert.ok(Object.hasOwn(inject,name),name);return inject[name];},module,module.exports);
  const request=(body:unknown)=>new Request(authority.origin+"/api/admin/mail",{method:"POST",
    headers:{"Origin":authority.origin,"Sec-Fetch-Site":"same-origin","Content-Type":"application/json","x-csrf-token":x.bound.session.csrf},
    body:JSON.stringify(body)});
  return {x,server:module.exports,request,store};
}

test("explicit administrator saves without returning SMTP password",async t=>{
  const {server,x,request}=await fixture(t);
  assert.equal(await server.adminMailAvailable(x.bound.session),true);
  const response=await server.handleAdminMail(request({action:"save",revision:0,settings:{
    host:"mail.fixture.invalid",port:465,username:"synthetic-user",password:"synthetic-private",sender:"sender@fixture.invalid"}}));
  assert.equal(response.status,200);
  assert.doesNotMatch(await response.text(),/password|synthetic-private/);
});

test("another owner, trader and stale MFA are denied before private body access",async t=>{
  for(const change of ["other-owner","trader","stale"]){
    const {x,server,request}=await fixture(t);
    if(change==="other-owner")x.user=id(9);
    if(change==="trader")x.role="trader";
    if(change==="stale")x.bound.session.oidcAuthTime-=901;
    const req=request({action:"save",revision:0,settings:{password:"private"}});
    assert.equal((await server.handleAdminMail(req)).status,400);
    assert.equal(req.bodyUsed,false);
  }
});

test("disabled handler skips authority, API and private body; CSRF also precedes intake",async t=>{
  const {x,server,request}=await fixture(t);
  process.env.COCKPIT_PLATFORM_ADMIN="0";
  const disabled=request({private:"secret"});
  assert.equal((await server.handleAdminMail(disabled)).status,404);
  assert.equal(disabled.bodyUsed,false);assert.equal(x.calls,0);
  process.env.COCKPIT_PLATFORM_ADMIN="1";
  const csrf=request({private:"secret"});csrf.headers.set("x-csrf-token","foreign");
  assert.equal((await server.handleAdminMail(csrf)).status,400);
  assert.equal(csrf.bodyUsed,false);assert.equal(x.calls,0);
});

test("private SMTP body rejects malformed UTF8 and length mismatch without storing settings",async t=>{
  const {x,server,store}=await fixture(t);
  for(const data of [Uint8Array.of(0xff),new TextEncoder().encode("{}")]){
    const req=new Request("https://cockpit.investalo.de/api/admin/mail",{method:"POST",
      headers:{"Origin":"https://cockpit.investalo.de","Sec-Fetch-Site":"same-origin","Content-Type":"application/json",
        "x-csrf-token":x.bound.session.csrf,...(data.byteLength===2?{"content-length":"3"}:{})},body:data});
    assert.equal((await server.handleAdminMail(req)).status,400);
  }
  assert.equal((await store.summary(Math.floor(Date.now()/1000))).configured,false);
});
