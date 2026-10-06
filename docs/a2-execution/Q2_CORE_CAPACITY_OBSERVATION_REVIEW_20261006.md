# 核心容量单次观察结果

2026-10-06，Asia/Shanghai。O1–O3 已完成；唯一 `lhqcap-20261006a` 已消费。
真实容量采集成功，四件原始证据完整留在原受保护本地管理 anchor；没有执行业务任务。

当前条件缺口定位到 journal：可用 **229134336 B**，原 05c 合同门槛 **299892736 B**，
差 **70758400 B（67.48046875 MiB）**。inode 足够，其余三个设备组的 bytes/inodes 也满足该条件比较。
这不是 05c 当时的可用量复原，不是完整 core admission 或 H01/Q4/H11 PASS。

## 准确版本和独立授权链

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，本轮直接完整读取固定私有规则。
- A：`1ba20d196facc82cf74aea88e7df3d4fe31e0584`，三文档及摘要见[原基线](../governance/Q2_CORE_CAPACITY_OBSERVATION_BASELINE.md)，字节与历史 OPEN 标签保持。
- B：[准确 Owner 决定](../governance/Q2_CORE_CAPACITY_OBSERVATION_OWNER_DECISION.md)，事件 `LH-Q2-CORE-CAPACITY-OBSERVATION-CLOSURE-20261006-01`。
- C：`cd4dc50df1d62591548c54afa3e5405608aba20b`，仅 AGENTS CLOSED 声明和 B 副本，没有实现。
- 实际执行 D：`dafa4360c1b62c59677236ab93da5af203fac240`，直接后继 C，只新增下列两个实现文件及窄测试。没有修改业务 runtime、bootstrap、dispatcher 或空 release allowlist。

| 文件 | bytes | SHA-256 |
| --- | ---: | --- |
| `tests/e3_host/q2_core_capacity_reader.py` | 13357 | `9c91b70cefce29e2f49fe0428caaa3b4196d6a5fed05a8d4a08691a4759d6744` |
| `tests/e3_host/q2_core_capacity_capture.py` | 33917 | `77c12ca96732fb9a7353a1536533fbdaa382a0b21f3f5fb4c4908d1e54464767` |
| `tests/test_e3_q2_core_capacity_observation.py` | 30112 | `60a54b914ee68049203390829ff1b68acf4ad347488253c5356175d82f7b144b` |

runner 仅复用原管理读取/执行文件保护等本地原语，不调用旧 sshd capture 的 run/main、旧配置解析或业务执行入口。
reader 无子进程和目录枚举，仅读取固定五个 parent、必要祖先及固定内核视图，按 A 复核 fd/名称/mount/UUID。

## O2 验证及固定输入

窄验证命令：

```text
python -B -m pytest -q tests/test_e3_q2_core_capacity_observation.py tests/test_e3_q2_sshd_source_capture.py tests/test_e3_q2_core_obligation_inputs.py tests/test_e3_q2_core_capacity.py
```

实际本地权限视图：**290 passed，1.39s**。受限工具视图此前为 289 passed、1 skipped，跳过的是
root-owned 原生执行文件身份检查，不将工具命名空间的视图当成宿主结论。
首次新测试保留为 107 passed、3 teardown/setup errors：测试夹具将 `os.open` 替换延续到捕获夹具结束，
修正 monkeypatch 作用域后通过；不是现场失败或业务结果。

`git diff --cached --check` 通过。准确 D 的 [CI 37398006101](https://github.com/kongbu0621/infra-local-hand/actions/runs/37398006101)
在 O3 前完成，classify-change、Ubuntu、Windows 三个 job 均 success，包含通常的源码及独立 wheel 安装验证。
本地没有为此另跑无关全套矩阵，没有重装现场。

本地 XML 证据保存在任务临时证据位置：

| 证据 | 本地 basename（任务私有临时证据目录） | SHA-256 |
| --- | --- | --- |
| 受限视图窄测试 | `lhqcap-20261006a-targeted.xml` | `3ca8114bb4246f21c8e52defbf3ca848d630ad6ce426848c65d179d21199b66b` |
| 实际本地视图窄测试 | `lhqcap-20261006a-targeted-native.xml` | `070f4cafd83bf49a821f57273ed0a047e4b4c6553800b39cfe2da3de3d5ff2af` |

这些是测试结果，不是 guest 现场证据。第一次私有输入预检在 `Downloads` 的符号链接处停止，零 marker/连接。
随后只读确认它指向既有保存位置，以规范路径读取同一批固定摘要原件；没有替换输入、降低权限检查或搜索其它档案。

准确原计划和六份固定 ZIP 的 26 个成员均通过原 pins；36 行历史义务、46 行 configured quota 保持全额。
新独立算术在全部 15 种分组与实际已发 `657b1bc` 的原 `_cap_charge` 纯算术一致。
这项离线对照使用明确合成的布局输入，未调用现场准入/helper，也不把合成布局当成实际布局。
随后本地管理预检核对原入口、管理 pins、四旧核心及旧诊断的 24 个 capture、264 MiB/80 inode 条件和本地 SSH 选项检查，
结果 `LOCAL_PREFLIGHT_PASSED`，请求数 0。O3 重新读取并核验，在同进程持有输入和原时钟下执行。

| 固定绑定 | SHA-256 |
| --- | --- |
| 原 plan | `efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c` |
| 五路径描述（311 B） | `64c6cfc7b773aa51af33cf971da672786c49965e16cc75923fc6fc25b1ac4814` |
| 重新验证的容量分量 | `3ecc6bd649d4e33bdc08283c8b76984fad286a1b484f7df0452b59a470033c82` |
| 15 分组门槛表 | `72e5dea35a99a97bc8bae7db000572d0c6ff747f010c0fc95a0bcff9b6b7ca07` |
| O3 inputs binding | `c872133f5bfdcc5a13d8a75aa217a9b8bf179c461613b83e7782dd553a02d773` |
| 24 个旧 capture 索引 | `fbb4fc58f001fb85f0e14b823dd626837068148a2dd37e8341b61b5df6ac0027` |
| 全部本次使用源码集合 | `23645861d80c4328d8571ba55f9439a322d2885bd8f63eee3c9c1a0d7542be94` |
| 固定 argv/environment | `db169288496d514ebc6e222bf71b4c8ade090648ffe64a2a0863fcd0f209dc8b` |

## O3 真实采集和证据回收

请求开始：**2026-10-06 09:26:49.887933 +08:00**。
一次 marker 创建、一次实际 SSH 请求；wait 0、stdout/stderr 双 EOF、严格五角色结构/输入/摘要校验通过。
host 原双时钟截至 receipt 记录点分别经过 407990782/407990441 ns；后续 write/fsync 的原 deadline 检查也通过。
reader 记录初始化后至生成结果 939466 ns，五角色逐次采样，不宣称原子快照。

状态为 `CURRENT_CAPACITY_OBSERVATION`，完成一次 ≤5s 的纯本地 `CONDITIONAL_05C_THRESHOLD_COMPARISON`。
没有再执行比较入口或远端复核。封存后仅本地 O_NOATIME 复核四个固定文件的摘要/保护，全部一致。
SSH 正常退出和双 EOF **不证明远端祖先独立监督闭合**；receipt 明确保留
`READER_REPORTED_COMPLETE_NOT_INDEPENDENTLY_SUPERVISED` 和 `remote_supervision_proven=false`。

四个原件保留在既有受保护 Q1 管理 anchor（同旧捕获父目录），可由原固定管理入口关系定位；
仅公开 basename 和摘要，原始路径/UUID/机器元数据不入公共仓库。

| 原件 | bytes | SHA-256 |
| --- | ---: | --- |
| `.lhqcap-20261006a.consumed.json` | 939 | `537f3f93f47034ae253c735052cbae443eea3aa3f775849698830e4b26cec9ff` |
| `.lhqcap-20261006a.stdout` | 3609 | `00cc8b744b8d63bf7d83a4044921fc1a80b7a21b289cf62b4e6f33cd9548b8db` |
| `.lhqcap-20261006a.stderr` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `.lhqcap-20261006a.receipt.json` | 1807 | `575e74006d530fd562a67d66d5ce066a8e941d914da1f84bec2eb839b7ee4270` |

合计 6355 B、4 个 single-link 0600 文件；本地观察分配量 12288 B。
完整承诺仍为 4 MiB/8 inodes，不按小文件退款。四旧核心及旧诊断的完整承诺、原件和 UNKNOWN 均保留。

## 当前设备的条件容量表

五角色形成四个设备组，state/install 共池。按每项义务在不同设备完整计一次、同池去重；
同池 AVAILABLE 取该组角色采样最小值。HISTORICAL 包含原 snapshot+delta、全额 configured quota 和三旧核心；
05C 列是已消费第四批的完整比较分量，**不是下一批的新预算**。
`REQUIRED=HISTORICAL+05C`，`DEFICIT=max(0, REQUIRED-AVAILABLE)`。

Bytes（B）：

| 角色组 | AVAILABLE | HISTORICAL | 05C | REQUIRED | DEFICIT |
| --- | ---: | ---: | ---: | ---: | ---: |
| state/install | 20717948928 | 1334579200 | 201326592 | 1535905792 | 0 |
| quota | 1889046528 | 465567744 | 55574528 | 521142272 | 0 |
| journal | 229134336 | 263192576 | 36700160 | 299892736 | **70758400** |
| evidence | 996749312 | 457179136 | 96468992 | 553648128 | 0 |

Inodes：

| 角色组 | AVAILABLE | HISTORICAL | 05C | REQUIRED | DEFICIT |
| --- | ---: | ---: | ---: | ---: | ---: |
| state/install | 2874636 | 74993 | 12288 | 87281 | 0 |
| quota | 130984 | 49792 | 7808 | 57600 | 0 |
| journal | 65506 | 19968 | 5504 | 25472 | 0 |
| evidence | 64801 | 21888 | 6272 | 28160 | 0 |

| 角色组 | 当前设备身份摘要 SHA-256 |
| --- | --- |
| state/install | `8d95caa22eb2ab7b71cea57e93281a0b894de6841ffe307b98d4329ef3b44bb5` |
| quota | `b8302c7b567151894a67932f73793761604b2b8334b18d4ba5ea866de4b53d3c` |
| journal | `3ff97dfdfff3a1684df0459a65a32c845d700f819b433f0b2ceed4841a29f564` |
| evidence | `ddc8858eb50e1b4ec5f4c3813b858d09f0c4f16af6dabf802f3280163da01c94` |

这里没有扫描历史 placement、查询当前 quota/enforcement 或核验旧进程，因此这些仍为 UNVERIFIED/UNKNOWN。
比较以当前设备分组继续承载原冻结合同为条件；当前空间检查不是排他预留，空间竞争仍可能导致失败。
当前 journal 缺口不能自动被改写为 05c 当时确切失败设备/数值的历史证明。

## 交付结论和下一步边界

已交付独立 C、专用 reader/runner、窄验证及准确 D CI、真实五目录容量和完整四件回收、当前缺口表。
本次只执行容量观察，**H01/Q4/H11 执行数为 0，没有新增业务结果**。
O1–O3 到此完成，唯一机会已经消费；没有重试、重连、补采、清理、退款或改变安装/SSH/配额/系统配置。

建议只针对 **journal 文件系统**准备扩容方案，保留全部原件与承诺。当前冻结 05c 比较至少缺
70758400 B，但不能仅补齐此差额便声称下一批可准入：实际扩容目标必须另行纳入未来获批批次的
完整新增承诺与运行余量，并以普通可用量 `f_bavail*f_frsize` 衡量，不能用 root 保留空间替代。
扩容或资源合同变更以及未来业务验收需要各自准确授权，本范围不实施它们，也不建立第五个业务批次。
之后仍须通过完整现场准入，再按获批新批次完成真实正常链、取消与同账本恢复及业务结果回收。
所有支线暂停，生产 `E3_SUPERVISION_UNVERIFIED` 保持；不能用这次诊断完成替代核心功能交付。
