# Core host writer transport：准确 OPEN 基线

- Authority：Owner；scope `LH-Q2-CORE-WRITER-TRANSPORT-v1`，T1–T3。
- R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，direct pinned rule SHA-256
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`；沿用根 AGENTS 的 mandate、权限与变更规则。
- A `60756caedf6a2d978627272e44784d11009ac309`，tree `82df6a8ec23fce903dbb09ca3feb51baacac503c`。
- Gate OPEN；无本 scope Owner B、独立 C 或新协议实现 D。本登记不生成、暗示或补写批准。

| 准确 authoritative 文档 | SHA-256 |
| --- | --- |
| [REQUIREMENTS](../a2-execution/q2-core-writer-transport/REQUIREMENTS.md) | `8d2f0dcc113eaab0fb086ef5163376e0ca5c17ab3a96fb4bcc90c1fb12a9d213` |
| [ARCHITECTURE](../a2-execution/q2-core-writer-transport/ARCHITECTURE.md) | `0327482634a6c62abde72b2bfdf8566abda90b6f0dd411fea8f15f1eda175b8f` |
| [IMPLEMENTATION_PLAN](../a2-execution/q2-core-writer-transport/IMPLEMENTATION_PLAN.md) | `1b0d745142929dfe6d377fad826cab2fce9a40d1fffffc583517721d8c97b109` |

唯一修订是 package strict v3 + entry.writer，来自原 held binding，供 guest 准确重建 marker v2。
writer canonical no-LF ≤4096 B，计入原 package/input 限额。其它 schema、固定候选/wheel/harness、
180 MiB/13440 physical、276 MiB/16512 admission、2090 CPU-s、2624 MiB/1160 pids、
32 MiB input/60 MiB outer output/64 MiB 16-inode capture、900/800/750 秒与一次性边界不变。

原 A `0bdb49cae5586be60a7ba31d4a8e8367854d1e8c` 及其 B/C 不改写；不受影响 D1–D4 可继续。
本 A 只请求实施/验证/重新冻结协议修订；原条件单次 F1 不增次、不延期、不退款。
全部原门和本门通过才可继续原 H01→Q4→H11。现有 package 未发行，release allowlist 为空。

供 Owner 审阅的准确决定文本（**请求，不是已发生决定**）：

> 按原 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，批准 A
> `60756caedf6a2d978627272e44784d11009ac309` 的 `LH-Q2-CORE-WRITER-TRANSPORT-v1`，
> 关闭该范围 Gate，执行 T1–T3；只补 package v3 的 host writer 传输与准确 marker 绑定。
> 原候选、预算、时限和条件单次 F1 不变，不增加执行次数；先独立 bookkeeping-only C 再实施。
> namespace/watchdog 暂停，production E3 限制保持。
