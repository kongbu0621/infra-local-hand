# Local Hand 核心现场输入只读复核（2026-10-03）

本页只记录 2026-10-03 已发生的一次交互式只读观察。它不是新 scope 的批准、安装、carrier
request、任务执行或验收结果；其 live transcript 也未被资格化为 raw attestation。proposed scope
`LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1` 见[需求](q2-core-acceptance-delivery/REQUIREMENTS.md)、
[架构](q2-core-acceptance-delivery/ARCHITECTURE.md)和
[实施方案](q2-core-acceptance-delivery/IMPLEMENTATION_PLAN.md)；当前仍是 Gate OPEN。

## 观察方式与限制

仓库外既有 Q1 管理目录中观察到一个 SSH 管理入口和一个 QEMU 启动描述。观察者先只读检查入口，
随后实际执行该 `ssh.sh` wrapper，以已有 identity/known_hosts、BatchMode 和 remote-command
non-PTY 路径建立只读连接。wrapper 的准确 profile 是
`env-bash-literal-ssh-v1`，其 source 使用 `StrictHostKeyChecking=accept-new`，不是
`StrictHostKeyChecking=yes`；known_hosts 当时已有目标条目，但本次 transcript 不资格化为独立的
“未写新 key”证明。没有上传文件、创建对象、启动/停止服务、修改配置、提交任务或读取业务结果。

| 当时观察到的本地对象 | SHA-256 | 限制 |
| --- | --- | --- |
| SSH 管理入口脚本 | `aed91e80483d4df103f95c1d4cd5bf9bd18720f4dc51720702c329c937f93c63` | 私有绝对路径、identity 和 host key 不公开 |
| QEMU 启动脚本 | `1acc8c4cb09bc5b14c32adc35e87d8500098cbf3968d53f406269e96df30f96a` | 当时配置，不证明当前 VM identity |
| fixture cloud-config `user-data` | `5b81deabefb7bc70aa6ee13b72053d65556fac1e400b5a37919ca1f90e4b6523` | source 含 `q1admin ALL=(ALL) NOPASSWD:ALL`；不是当前 guest policy attestation |
| identity public key / 从私钥派生的 public key | `e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c` | 不读取或公开私钥 bytes；只固定 public identity |
| known_hosts 文件 | `d1025c074e532f29534fcab1d10ec1bc2f38d2137173c74d0bc921bbab420bbd` | 未公开内容 |

本轮 live transcript 没有按独立 attestation 合同证明命令集合完整、字节未截断、封存完整性或
现场状态持续有效。因此本文只把它作为观察来源，不把它称为 raw attestation。上表内容摘要是
proposed A 的静态 private-source pins；它们不是 guest attestation。绝对 path/dev/inode、当前
存在性、当前 guest policy、host key 状态以及 wrapper 最终 argv 的现场实体关系仍须 C 后、在同一
已消费 carrier 内重新验证。

## 当时观察到的 guest

- 连接目标当时表现为隔离 QEMU test guest，而不是当前 Codex 工具环境；这是时点观察，不证明
  后续连接时仍保持相同隔离关系。
- guest PID 1 当时为 systemd 255；观察到统一 cgroup v2，根显示 `0::/init.scope`。
- 取得了当时 boot identity，但只留在私有交互上下文；本文不公开，也不授权未来采用。
- 专用 Q2 普通账号/主组存在，对应 user manager 当时 active/running。
- 四个已知 Q2 parent slice 当时 active；这不证明新 candidate 的监督链已资格化。
- quota 数据盘当时为启用 project quota 的 ext4；journal、evidence 和 system 位于分开的磁盘关系。
- 历史 `20261001e` installation/resume/consumed 记录存在并保持已消费；其七个旧 roots 当时不存在。
  这个组合不是可复用的新批次。
- 未观察到本 proposed scope 的准确候选安装、wheel/projected-source receipt、C 后 D/package/dispatcher、三个新 ledger、
  三个 operation 或二十一个新 roots。

这些只是时点观察。boot、路径、PID、InvocationID、cgroup/filesystem identity、容量和对象不存在性
都须在准确 B/C 后重新观察并绑定，不得写成 A 的固定事实。

## 工具环境与真实 guest

当前 Codex 工具环境不是上述 guest，也不是据以判断 guest E3 支持性的真实宿主。工具环境 PID 1、
namespace、system bus 或 cgroup 权限的结果都不能推导 guest 支持或不支持 systemd 监督。本轮远端
观察只纠正环境混淆；它没有证明安装、manager delivery、quota roots、任务退出或 evidence 收回。

## 当前准确状态

- `LIVE_ISOLATED_GUEST_OBSERVED`
- `CORE_CANDIDATE_ARTIFACTS_PREPARED`
- `CORE_FIELD_INPUTS_NOT_PREPARED`
- `CARRIER_REQUEST_NOT_ISSUED`
- `REAL_TASK_NOT_EXECUTED`
- `RESULT_EVIDENCE_NOT_COLLECTED`

此前只读 SSH 观察不是 proposed scope 的 carrier request。没有 Local Hand task 被受理、受监督执行
或退出确认，也没有业务 result/evidence 被收回。

## 最小后续准备

已完成的本地静态准备是 candidate
`4b6e4a7c403362358192086b88679e1326dcb2e1`（唯一 direct parent
`607100a57206f7dc7cfcbd6cae8507cfa599b813`）、唯一 wheel/payload 与 canonical projected-source
manifest 的冻结和验证；准确 wheel bytes 当前保留在 workspace `dist/`，并另有同一 A 中的
artifact receipt 固定两次独立 build 的字节一致性和 exact-hash-only 复用规则。receipt 只保留
installed verification 的汇总、长度和摘要；364843-byte raw report 不属于 A 的 artifact set，
不能把该摘要称为随 A 留存的 raw report。它们没有被送入
guest。剩余最小步骤为：

1. 提交三份文档与本复核形成准确 A；取得精确 Owner B 和独立 bookkeeping-only C。
2. C 后按 A 的严格 schema/framing 实现/测试 dispatcher 与 field package，冻结 D/package 摘要。
   只在本地完成静态核验；在任何本 scope 新现场读取/连接前固定不可刷新 carrier deadline 并持久
   消费一次性记录，然后发出唯一 request。动态观察、累计容量准入、package 传输和 create-only 安装
   都必须在这同一 carrier 内完成，不能先远端观察/安装再发 request。
3. 依次 JIT 执行 `H01_NORMAL`、`Q4_HELPER_RUNNING_CANCEL_SUBSET`（`full_h07=false`）、
   `H11_SAME_LEDGER_RECOVERY`；任一不完整即停止且不另连。

namespace/watchdog 保持暂停，production `E3_SUPERVISION_UNVERIFIED` 保持。本页没有创建 baseline、
B、C、现场 plan 或执行权限。
