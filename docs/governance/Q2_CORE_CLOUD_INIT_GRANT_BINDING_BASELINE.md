# Core cloud init grant binding proposal baseline

Status: **OPEN / NOT APPROVED**. Authority: Owner.
Scope: `LH-Q2-CORE-CLOUD-INIT-GRANT-BINDING-v1`, G1–G3 only.

R remains `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`, read directly from
`kongbu0621/engineering-sop/docs/workflow/program-repository-documentation-gate.md` at that commit.
Original rule SHA-256 remains `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`.
Mandate, Owner-only authority, no exceptions and all change-control obligations remain unchanged.

Exact documentation A: **`018bdd7f09998290f536ab5a3726ccb4123dffa3`**.
Tree: `a444a2398766ee4cba7e4f674a326c3a18995098`.
Implementation source reviewed, not a new D: `e2a40bd4b0e0b17ebe2a2ad3f533bdace318cc05`.

| Authoritative file under docs/a2-execution/q2-core-cloud-init-grant-binding | SHA-256 |
| --- | --- |
| REQUIREMENTS.md | `2330303e9bf7dd7e19c59cac6c1e864fb8c04ad08203575b15255941837fb80a` |
| ARCHITECTURE.md | `1960ca98f717866a76c57c55c04a3df09718267d86c046abcc5209115f1c645f` |
| IMPLEMENTATION_PLAN.md | `5af1d1348a7f955c6516334f68c7926fa0154a1fe7c055fdf352f136e2f70285` |

The sole premise correction recognizes the existing fixed cloud-init account/sudo mapping as the source
of a canonical grant, instead of asserting that the file contains a complete sudoers literal line.
The original whole-file hash, account, effective permission requirements and current guest verification stay fixed.
It changes neither runtime candidate/wheel nor any original object, budget, deadline, transport count or production gate.
See [requirements](../a2-execution/q2-core-cloud-init-grant-binding/REQUIREMENTS.md) and the
[actual private-package review](../a2-execution/Q2_CORE_PRIVATE_PACKAGE_REVIEW_20261005.md).

Suggested exact Owner decision, **not a received decision**:

> 按原 R，批准 A `018bdd7f09998290f536ab5a3726ccb4123dffa3` 的 `LH-Q2-CORE-CLOUD-INIT-GRANT-BINDING-v1`，接受固定 cloud-init 同一账号 mapping 到规范 sudo grant 的来源归一化，关闭该范围 Gate，执行 G1–G3；先独立 C 再实施。原版本、预算、时限及条件单次 F1 不变，支线暂停，生产 E3 限制保持。

No B or CLOSED C exists for this correction. Approval must be retained verbatim with exact R/A/scope and
stable Owner/event evidence, followed by an independent bookkeeping-only C before implementation.
This registration neither consumes a field attempt nor asserts current marker absence.
