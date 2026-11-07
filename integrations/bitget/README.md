# Bitget Classic V2 read adapter

Standard-library Python core, imported with `PYTHONPATH=integrations/bitget/src`.
No API/UI/DB integration, credential vault, real account test, broker order,
transfer, withdrawal or combined trading budget is implemented here.
The separate [credential service](../../services/credentials/README.md)
integrates this probe with encrypted storage and one-use action assertions.
Its tests use synthetic broker responses; actual HTTP/UI and account connectivity
remain unfinished.

`ClassicReadClient` requires an injected transport and authenticated server-side
`OwnerContext(tenant_id: UUID, user_id: UUID)`. Credentials and requests have
redacted representations and reject ordinary pickle/dataclass serialization.
Trusted transports can read the header values necessary for dispatch; do not
copy those values to logs, exceptions, research, browser storage or AI.
Python in-memory objects are not a vault or guaranteed memory zeroization.

Only these signed GET targets exist:

| Target | Fixed query |
| --- | --- |
| `/api/v2/spot/account/info` | none |
| `/api/v2/spot/account/assets` | `assetType=all` |
| `/api/v2/mix/account/accounts` | validated `ProductType`: USDT/USDC/COIN-FUTURES |

HMAC-SHA256/Base64 uses the exact timestamp + `GET` + path + optional `?query`
bytes. `HTTPSReadTransport` fixes `https://api.bitget.com`, verifies CA and
hostname, requires TLS 1.2+, disables proxies and redirects, limits responses to
1 MiB, and bounds socket-operation timeout to 1–20 seconds (default 10).
It makes no retries, including HTTP 429, and raises static redacted error codes.
The request is signed; the broker response is received through verified HTTPS,
not separately cryptographically signed.

`probe_identity(context, expected_egress_ip=...)` reads only accountinfo. It
validates Classic `userId`, nullable `parentId` (integer zero is preserved
distinctly from missing/null, without inferring universal parent status),
known read-only `authorities` and a nonempty IP whitelist
containing the explicitly expected egress IP. Its returned UID can establish a
frozen `AccountBinding`; wallet reads require that binding and fresh accountinfo
checks of owner, UID, parent, privileges and IP before each request. Additional
whitelist IPs are not prohibited by this core. Expected egress must come from
trusted server configuration, not an unverified browser claim.

IP gates default to enabled for every injected transport, including wrappers.
Offline fixtures may explicitly use `require_ip_gate=False`; the built-in HTTPS
transport rejects this opt-out. Custom transports are trusted implementation
code and must never bypass the gate for real network access. Tenant/UID
uniqueness is a pure validator; the credential service supplies atomic database
binding and authenticated rotation. Server provisioning, clock synchronization
and global scheduling remain host platform responsibilities.

The declared Classic mode and exact Classic V2 schema are evidence of the
selected adapter family, not a universal proof of the account's broker mode.
UTA `permType`/`permissions` are not normalized to Classic authorities.
Accepted read codes: `stor`, `coor`, `cpor`, `smor`, `ttor`, `wtor`, `taxr`,
`chor`, `p2pr`. Unknown, management and write codes fail closed; notably `wtow`
(transfer write) and `wwow` (withdrawal write) are rejected. No undocumented
mapping from individual read codes to balance endpoints is invented.

Accountinfo attempts are locally paced at one per second per client, including
failed attempts, using a monotonic clock and lock. A too-early call fails without
dispatch. Multiple keys/clients for the same UID still require a shared future
scheduler; this is not a global quota guarantee.

Spot and each Futures product return separate immutable wallet records.
Financial wire strings become exact `Decimal`; absent/null/empty values remain
`None`, while actual zero remains zero. Futures available balances, equity and
unrealized PnL may be negative. `accountEquity` already includes unrealized PnL;
`usdtEquity` and `btcEquity` are alternate units, not amounts to add. Futures
`assetMode=union` denotes futures multi-asset margin, not UTA. Coin case is
preserved, including mixed-case broker asset codes. `uTime` is preserved as the
documented milliseconds without guessing seconds from an example's length.
There is no wallet summation, position reader, usable strategy budget or live
execution approval.

Official sources checked for this implementation:

- [Classic REST signing/headers](https://www.bitget.com/docs/classic/rest-api)
- [Classic / UTA upgrade distinction](https://www.bitget.com/docs/classic/uta-api-upgrade-guide)
- [Classic accountinfo schema, authorities and 1/sec/UID limit](https://www.bitget.com/legacy-docs/classic/spot/account/Get-Account-Info)
- [Classic Spot assets](https://www.bitget.com/legacy-docs/classic/spot/account/Get-Account-Assets)
- [Classic Futures account balances](https://www.bitget.com/docs/catalog/classic-contract-account/classic-contract-account)
- [Mixed-case asset changelog](https://www.bitget.com/docs/uta/changelog/2026-04)

Offline checks:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=integrations/bitget/src python3 -m unittest discover -s tests/bitget -v
```

Tests use invented credentials, captured request objects and mocked HTTPS
openers. They never contact Bitget or claim that a real key/account is connected.
