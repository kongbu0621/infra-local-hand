# Local Hand 核心验收交付：Owner 决定

- Decision Authority / Owner：当前项目 Owner（本工作会话用户）。
- 决定记录时间：2026-10-03 21:16:05 +08:00（紧随准确用户回复取得的本机时间）。
- 本地可追溯事件：`LH-Q2-CORE-ACCEPTANCE-DELIVERY-CLOSURE-20261003-01`；
  不是平台消息 ID。
- 稳定来源：本文件同时保留紧邻的准确批准请求与本次准确 Owner 回复，供 Owner 核验。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本次 executor 已直接读取
  private companion source 的该固定 commit，规则内容 SHA-256 为
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`，与本地采用记录匹配。
- Documentation A：`74366b3fe41e675b1aa2d677228714a5606c275c`，tree
  `7df4fd0c876df13af4ec73c6f910272a72d7ea4d`，direct parent
  `4b6e4a7c403362358192086b88679e1326dcb2e1`。
- Scope：`LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1`。

## 紧邻的准确批准请求

> 按原 R 10d2a5c827964989f41ca6e8eeac3d44de6d0f04，批准 A 74366b3fe41e675b1aa2d677228714a5606c275c 的 LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1；接受 A 中披露的唯一新治理前提、固定 candidate/wheel/harness/对象、physical 180 MiB/13440、admission 276 MiB/16512、2090 CPU-s、peak 2624 MiB/1160 pids、32 MiB input/60 MiB output/64 MiB/16-inode capture 预算及 900/800/750 秒外层时限；授权最多一次 O_EXCL marker、最多一次 carrier request、不重连不重试，并继续建立独立 bookkeeping-only CLOSED C，再按 A 实施 D、验证、冻结 package，且仅在全部门通过后条件执行 H01_NORMAL→Q4_HELPER_RUNNING_CANCEL_SUBSET→H11_SAME_LEDGER_RECOVERY。H11 只使用原 ledger 和原 unit 身份，不重启业务、不延长 deadline；namespace/watchdog 保持暂停，production E3_SUPERVISION_UNVERIFIED 保持。不授权复用旧批次、第二 request、系统配置变更、生产启用或把 UNKNOWN 提升为成功。

## Owner 准确回复 B

> 按原 R 10d2a5c827964989f41ca6e8eeac3d44de6d0f04，批准 A 74366b3fe41e675b1aa2d677228714a5606c275c 的 LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1；接受 A 中披露的唯一新治理前提、固定 candidate/wheel/harness/对象、physical 180 MiB/13440、admission 276 MiB/16512、2090 CPU-s、peak 2624 MiB/1160 pids、32 MiB input/60 MiB output/64 MiB/16-inode capture 预算及 900/800/750 秒外层时限；授权最多一次 O_EXCL marker、最多一次 carrier request、不重连不重试，并继续建立独立 bookkeeping-only CLOSED C，再按 A 实施 D、验证、冻结 package，且仅在全部门通过后条件执行 H01_NORMAL→Q4_HELPER_RUNNING_CANCEL_SUBSET→H11_SAME_LEDGER_RECOVERY。H11 只使用原 ledger 和原 unit 身份，不重启业务、不延长 deadline；namespace/watchdog 保持暂停，production E3_SUPERVISION_UNVERIFIED 保持。不授权复用旧批次、第二 request、系统配置变更、生产启用或把 UNKNOWN 提升为成功。

## 决定边界

本 B 精确绑定上述 R、A 和 scope。Owner 接受 A 披露的唯一新治理前提：当前隔离 fixture 的
source/policy 含 `q1admin ALL=(ALL) NOPASSWD:ALL`；固定 caller 虽只允许一个 management entry、
固定 argv 和一次 request，但既有 policy 本身不是 exact-command/one-shot 的技术 containment，不能
技术排除其它登录、并发 sudo 或重复调用。该接受不授予通用 sudo、系统配置变更或生产权限；现场
source/policy/隔离事实漂移仍须停止且不得重试。

Owner 同时接受 A 固定的 candidate、wheel、harness、logical namespace、installation/staging、
install UUID、三个 case/operation/controller、21 个 project/root 对象、unit 集合、成员闭包、状态机、
停止/保留和证据合同，以及 physical 180 MiB/13440、admission 276 MiB/16512、2090 CPU-s、
peak 2624 MiB/1160 pids、32 MiB input、60 MiB output、64 MiB/16-inode capture 和
900/800/750-second 外层边界。Owner 授权在本独立 C 后实现并验证 D、冻结准确 package，在所有
静态与 live admission 门成立时创建最多一次 `O_EXCL` marker、发出最多一次 carrier request，且按
`H01_NORMAL` semantic PASS → `Q4_HELPER_RUNNING_CANCEL_SUBSET` semantic PASS →
`H11_SAME_LEDGER_RECOVERY` 的条件顺序执行。A 范围内不需要逐文件或逐 case 再问 Owner。

H01 保留正常入口的 empty-ledger gate。H11 只附着原 ledger 和原 request/execution/unit 身份，
不得重新 submit/start 业务、读取/hash/复制/封装原业务 result bytes、重建 unit、生成新 grant 或延长
deadline；只收 recovery observation/verdict 与仍持有的外层控制证据。marker 创建即消费；任何短写、
拒绝、断线、BLOCKED、UNKNOWN 或后续失败都不退款，不产生 reconnect、retry、第二 marker、第二
request 或换名绕过。

历史 `20261001e` 和其它过期/已消费批次不得重放。namespace/watchdog 保持暂停且不从本范围取得
实现、fixture、预算或现场权；production `E3_SUPERVISION_UNVERIFIED` 保持。本 B 不授权生产启用、
cutover、E4–E6、系统配置变更或把 UNKNOWN/缺证据解释为成功。

本文件与根 `AGENTS.md` 的 CLOSED 登记共同构成独立 bookkeeping-only C。A 的六个文件及其
[OPEN baseline registration](Q2_CORE_ACCEPTANCE_DELIVERY_BASELINE.md) 保持字节不变；后续
implementation D 必须以本 C 为直接父提交。本 C 不包含 production/test source、executable prototype、
dependency、runtime configuration、package、private delivery、marker、guest connection 或现场动作，
也不消费任何预算或一次性授权。C 时点的 marker/carrier request/H01/Q4/H11 run/result/evidence 计数
仍全部为 0。
