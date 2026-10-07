# 最小核心接续：K1 完成，K2 首次 guest 身份检查失败

2026-10-07（Asia/Shanghai）。**唯一 K2 维护窗口已消耗并失败；journal 扩容未执行，
K3 / H01 / Q4 / H11 均 NOT_RUN。** 本记录仅登记冻结、实际返回和已取得原件的核对，
不授权重试、补采、清理、恢复或新窗口。

## 准确授权、候选与冻结

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，本会话已读直接固定规则并核验摘要。
- A：`5d6cefa602e9146f02887ebfaa4b0cad4e376ff2`，scope
  `LH-Q2-CORE-MINIMAL-CONTINUATION-v1` / K1–K3；三文档字节保持不变。
- [准确 Owner B](../governance/Q2_CORE_MINIMAL_CONTINUATION_OWNER_DECISION.md)：
  `LH-Q2-CORE-MINIMAL-CONTINUATION-CLOSURE-20261007-01`。
- 独立、仅登记的 C：`8a4c24cefe4abbab193577b2dff48fc49626cae4`。
- 实际执行 D：`a743af326cdff6e4485b69332e2309130d82a915`，tree
  `ea35434943e4fda911d3fb593630c3e46a998416`；已发布 main，承接 C。

[K1 实现与本地验证](Q2_CORE_MINIMAL_CONTINUATION_REVIEW_20261007.md)记录准确初始实现 D1
的相关源码 2050 passed / 35 skipped，以及独立 installed 94 checks / 292 commands PASS。
最终 D 修正阶段剩余时间绑定、删除失去调用者的认证选项并登记已审 dispatcher；相关
237 项发行/绑定检查和 154 项维护检查通过。失败与 SKIP 的原始日志保持私有。

[最终 D 的 CI 37595331543](https://github.com/kongbu0621/infra-local-hand/actions/runs/37595331543)
于现场执行前完成，首个 run attempt 的 classify-change、Ubuntu、Windows 三个 job 全部成功，
包括两平台源码及独立安装验证。此 CI 绑定完整 D，不以 D1 的 CI 代替。
发行前再次核对 main、HEAD/tree、C 祖先、三文档摘要、源码及本地报告摘要。
唯一已审 dispatcher SHA-256：
`ea5d6c0abe2ca49af86e2d0c2088bc7ce9ae723a3803d5a9ddc715c480d2c524`。
私有冻结记录 SHA-256：
`81e3e34554346b36a5672bd576daf19735c4b64fed416cb1b9b11b9ff5912925`。
维护前已完成核心接续的静态构包与保留输入验证；没有提前构造或发行真实 07a 核心包。

## 一次实际维护返回

事件 `LH-Q2-CORE-MINIMAL-CONTINUATION-RETURN-20261007-01`。
普通预检一次通过后，使用同一 D/manifest/nonce/双钟和累计用量进入一次 execute。
没有 host sudo、全宿主 writer 扫描或替代扫描器。

| 事实 | 实际返回 |
| --- | --- |
| 维护 session | `lhqjgrow-20261006a` |
| CLI exit / phase | `3` / `execute` |
| state / reason | `STOP_AND_RETAIN` / `GROWTH_REPORT_MISSING` |
| marker / SSH / business cases | `true` / `1` / `0` |
| started | `CONSUMED`, `GUEST_QUIET` |
| guest stderr stage / reason | `PRE_IDENTITY` / `GROWTH_JOURNAL_SERIAL` |
| guest status / actions_started | `INCOMPLETE` / `[]` |
| guest stdout / stderr | `0` B / `517` B |
| 记录的 transport exit / remote exit | `null` / `UNKNOWN` |
| host writer observation / continuous exclusion | `NOT_PERFORMED` / `false` |

`GUEST_QUIET` 出现在 started 列表仅表示该步骤开始，不表示已静止或成功。
原 events 只有 CONSUMED STARTED/RETURNED、GUEST_QUIET STARTED 和 pre phase 绑定；
没有 guest 成功报告或 POWER_OFF_TOKEN。源码顺序及原件证明本调用尚未发出关机、备份、
镜像增长、重启或 ext4 增长。guest 的动作列表为空；不将这些事实扩张为整机活动盘点。

已有 guest stderr 将首因定位到 `JournalDevice` 的序列号比较：从 journal block device
的 sysfs `serial` 读取的字节不等于批准输入序列号的 ASCII 字节加换行。
捕获内容没有实际序列号字节，不能判定差异是值、截断、填充或格式；也不能据此取消身份检查。
没有重新连接、读取新的 guest 事实或修复现场来解释该差异。
host 在成功报告缺失时返回外层错误；其记录未证明 transport/remote 的独立退出，不补写 PASS。

## 已有原件与保留边界

固定五份现场原件通过既有受保护读取路径核对，使用 O_NOATIME、O_NOFOLLOW、原件元数据
稳定性及已有 stream 摘要校验；这是读取本次已有输出，不是额外采集或第二次维护。
原件继续留在原管理 anchor；私有副本和调用方输出留在本机
`/mnt/data1/tmp/lhqcore-minimal-20261007`。本公开记录不含原始机器内容。

| 原件后缀 | 字节 | SHA-256 |
| --- | ---: | --- |
| `consumed.json` | 34007 | `e5c7a9d540be9f1c7a7202039e43d7fc0d3ea359528582033d2fb1d9c5a12734` |
| `events.jsonl` | 441 | `02d8e0783337c774a44aeccda1f7788c10c5f9f424d479a01a14088d2bf013b2` |
| `pre.stdout` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `pre.stderr` | 517 | `4464dd988e5867af7e0f0c7bbd0b4c848391553c65095c5a57b5ff43958321af` |
| `receipt.json` | 6577 | `9d34abbf1917c5d352961fb8dface00d9b674549bf99f7b85335928d5e204573` |

实际 basename 前缀均为 `.lhqjgrow-20261006a.`。CLI execute 原始 stdout 与 receipt 同摘要；
CLI 自身 stderr 为空，不等于 guest stderr 为空。私有 `execution-result.json` 索引
2619 B，SHA-256 `b4681cef6def383cfcf15109ebd55c7a6cd15dc69cc3a416eec6bd6f1f6c6db2`，
包含上述原件、普通预检、execute、冻结和准确 CI 返回的长度/摘要及关系。

没有完整合格维护原件，因而不生成真实 journal transition、不采用新 boot、不发行核心包。
K3 的条件未成立，H01/Q4/H11 均 NOT_RUN，不能称核心功能已完成。
本次以及全部旧窗口继续消耗；当前调用方文件只作证据保留，不得重新运行。
本结果登记仅修改文档，不修改已冻结 D、现场原件或批准的 A。
