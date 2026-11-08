"""Actual pinned Next routes fail closed without providers, config or secrets."""
import subprocess
import sys
from uuid import uuid4


def docker(*args, timeout=45):
    return subprocess.run(
        ["docker", *args], check=True, timeout=timeout,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ).stdout


def main():
    name = "investalo-credential-browser-disabled-" + uuid4().hex
    started = False
    try:
        docker(
            "run", "--detach", "--rm", "--pull=never", "--name", name,
            "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--memory", "160m",
            "--cpus", "0.3", "--pids-limit", "32",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
            "--env", "HOSTNAME=127.0.0.1",
            # A preview flag cannot manufacture a signing or transport identity.
            "--env", "COCKPIT_PASSKEY_PROOF_PREVIEW=1",
            "investalo-cockpit:0.1.0-local",
        )
        started = True
        result = docker("exec", name, "node", "--input-type=module", "-e", """
import assert from 'node:assert/strict';
import { setTimeout as pause } from 'node:timers/promises';
const base = 'http://127.0.0.1:3000/api/credentials/passkey/';
let ready = false;
for (let attempt = 0; attempt < 60; attempt++) {
  try {
    const response = await fetch(base + 'start', { method: 'POST',
      body: '{invalid', signal: AbortSignal.timeout(500) });
    if (response.status === 503) { ready = true; break; }
  } catch {}
  await pause(250);
}
assert.equal(ready, true);
for (const phase of ['start', 'finish', 'execute']) {
  const response = await fetch(base + phase, { method: 'POST',
    body: '{invalid', signal: AbortSignal.timeout(3000) });
  assert.equal(response.status, 503);
  assert.match(response.headers.get('cache-control'), /no-store/);
  assert.equal(response.headers.get('x-content-type-options'), 'nosniff');
  assert.deepEqual(await response.json(), {
    error: 'Die Kontoanbindung ist in dieser Umgebung noch nicht freigeschaltet.',
  });
  const get = await fetch(base + phase, { signal: AbortSignal.timeout(3000) });
  assert.equal(get.status, 405);
}
console.log('PASS: 6 actual Next default-off route checks');
""", timeout=35)
        if result.strip() != b"PASS: 6 actual Next default-off route checks":
            raise RuntimeError()
        print(result.decode().strip())
    finally:
        # Detached run may create the container before acknowledgment times out.
        # Always address only this invocation's unique name, even on that path.
        cleanup = subprocess.run(
            ["docker", "stop", "--time", "5", name], check=False, timeout=15,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if started and cleanup.returncode:
            raise RuntimeError()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("FAIL: isolated Next route checks rejected", file=sys.stderr)
        sys.exit(1)
