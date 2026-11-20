import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { mkdtemp, writeFile, chmod, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createHash, randomBytes } from "node:crypto";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";
import { loadMailAuthority } from "../src/lib/admin-mail-authority.ts";

const require=createRequire(import.meta.url);
function load(path:string,inject:Record<string,unknown>){
  const code=ts.transpileModule(readFileSync(new URL(path,import.meta.url),"utf8"),{
    compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  const module={exports:{} as any};
  new Function("require","module","exports",code)((name:string)=>Object.hasOwn(inject,name)?inject[name]:require(name),module,module.exports);
  return module.exports;
}
const summary={revision:0,configured:false,host:"mail.fixture.invalid",port:465,username:"",
  sender:"owner@fixture.invalid",recipient:"owner@fixture.invalid",verification:"none",expiresAt:null,verifiedAt:null};
const form=load("../src/components/admin-mail-form.tsx",{});

test("admin SMTP SSR presents empty password, explicit SSL and separate confirmation steps",()=>{
  const rendered=renderToStaticMarkup(React.createElement(form.AdminMailForm,{csrf:"synthetic-csrf",initial:summary}));
  assert.match(rendered,/SSL\/TLS/);
  assert.match(rendered,/type="password"/);
  assert.match(rendered,/Bestätigungscode per E-Mail senden/);
  assert.match(rendered,/E-Mail bestätigen/);
  assert.doesNotMatch(rendered,/synthetic-mail-secret|localStorage|sessionStorage/);
});

test("actual admin page protects visitors and other owners; admitted admin receives only summary",async()=>{
  let session:any=null,allowed=false;
  const page=load("../src/app/admin/settings/page.tsx",{
    "next/link":{default:({href,children}:any)=>React.createElement("a",{href},children)},
    "next/navigation":{notFound:()=>{throw new Error("404");}},
    "@/lib/auth":{getSession:async()=>session},
    "@/lib/admin-mail-server":{adminMailAvailable:async()=>allowed,adminMailSummary:async()=>summary},
    "@/components/dashboard":{Shell:({children}:any)=>React.createElement("main",{},children)},
    "@/components/login":{Login:()=>React.createElement("p",{},"Login fixture")},
    "@/components/admin-mail-form":form,
  });
  assert.match(renderToStaticMarkup(await page.default()),/Login fixture/);
  session={csrf:"synthetic-csrf"};
  await assert.rejects(page.default(),/404/);
  allowed=true;
  assert.match(renderToStaticMarkup(await page.default()),/Administration/);
});

test("actual private admin files enforce ownership, key pin and restrictive modes",async t=>{
  const directory=await mkdtemp(join(tmpdir(),"investalo-mail-authority-"));
  t.after(()=>rm(directory,{recursive:true,force:true}));
  const key=randomBytes(32),config={schema:"investalo-platform-admin/1",tenantId:"00000000-0000-0000-0000-000000000001",
    userId:"00000000-0000-0000-0000-000000000002",subject:"synthetic-subject",
    issuer:"https://auth.cockpit.investalo.de",origin:"https://cockpit.investalo.de",
    recipient:"owner@fixture.invalid",defaultHost:"mail.fixture.invalid",
    keySha256:createHash("sha256").update(key).digest("hex")};
  await writeFile(join(directory,"config"),JSON.stringify(config),{mode:0o400,flag:"wx"});
  await writeFile(join(directory,"smtp-key"),key,{mode:0o400,flag:"wx"});
  assert.equal((await loadMailAuthority(directory)).authority.userId,config.userId);
  await chmod(join(directory,"smtp-key"),0o600);
  await assert.rejects(loadMailAuthority(directory));
  await chmod(join(directory,"smtp-key"),0o400);
  await chmod(join(directory,"smtp-key"),0o600);
  await writeFile(join(directory,"smtp-key"),randomBytes(32));
  await chmod(join(directory,"smtp-key"),0o400);
  await assert.rejects(loadMailAuthority(directory));
});
