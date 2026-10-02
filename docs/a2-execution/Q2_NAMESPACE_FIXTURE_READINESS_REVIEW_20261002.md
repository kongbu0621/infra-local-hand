# Namespace NS2：现成 fixture 准入资料复核

2026-10-02 +08:00；只读审计基线 `d142b99a10edda2e846caaa42538ba0eb81d1349`。
本件核对 NS2 所需的现成隔离环境是否具备；这是只读审计，不是 Owner closure。
准确提案仍为 [A `dfdd653dd48388d8ab1a2554d16bf5b610edba10`](../governance/Q2_NAMESPACE_REFERENCE_BASELINE.md)，
scope `LH-Q2-NAMESPACE-REFERENCE-v1`；三份 authoritative 文档字节不变，Gate **OPEN**。

**结论：NS2 准入资料 NOT_PREPARED；现成环境对 NS2 的适用性 NOT_PROVEN，native
qualification BLOCKED / NOT_RUN。** 已有材料不能支持“现成 NS2 fixture 已具备”。
这不证明物理环境不存在或必然不支持；也不能把 collector 尚未实现当作环境不存在的证据。

## 已有材料确实证明什么

- [Q1 closeout](E3_QUOTA_Q1_CLOSEOUT_REVIEW.md#L15)保留 Owner 在隔离 KVM guest 的历史
  实机返回，包含普通身份/PrivateUsers、配额、原 client exit 与双 EOF 的限定报告。
  该文头部的后续 Q1 复核进展保持；更早的 E3 NOT_PREPARED 不覆盖这次历史进展。
- [Q2 startup repair](Q2_SUPERVISOR_STARTUP_REPAIR_VERIFICATION.md#L21)登记实际准备到
  `RETRY_PREPARED`、七根保持空等观察；同一记录仍为 INCOMPLETE，原独立 stop record
  为空、缺 invocation declaration/seal。后来的树空不是原停止证明。
  [回传 manifest](evidence/q2-readonly-return-20260927/manifest.json)的
  `/reported_current_state/full_live_admission_verified=false`仍保留；该时点不是今天的 live admission。
- 支持 Python 3.12.14 / pytest 8.4.2 的[本地回归](evidence/q2-field-gap-20261002/closure-order-verification.json)
  为 651 PASS / 21 SKIP；准确 `41309e2` 的[普通 CI](evidence/q2-field-gap-20261002/native-ci-41309e2.json)
  为 Linux 3783 PASS / 51 SKIP、root collector 16 PASS、installed wheel 94 checks / 292 commands PASS。
  这些是各自开发/组件/安装范围的结果，没有 namespace N01–N12 qualification。

## 逐项适用性与具体缺项

下表 source pin 均为审计基线 `d142b99…`；NS2 条件来自准确 A 的
[需求](q2-namespace-reference/REQUIREMENTS.md#L89)和[实施计划](q2-namespace-reference/IMPLEMENTATION_PLAN.md#L59)。

| NS2 必需条件 | 已有来源及限定能力 | 未准备的适用依据 |
| --- | --- | --- |
| 明确 supplied fixture、普通身份与 runtime/interface | Q1/Q2 有历史 guest/账户/manager 记录；开发 runtime 和普通文件测试有实证 | 尚无被指定为 NS2 的 fixture 来源、普通 UID/GID/groups、固定 runtime/ABI 与既有监督/收件/审计来源适用清单；不把历史 guest 或开发容器直接采用成 NS2 reference |
| existing ordinary supervisor / stdio-only launcher | [q2_supervisor](../../tests/e3_host/q2_supervisor.py#L3)是既有 root service 合同；[command](../../tests/e3_host/q2_supervisor.py#L381)固定 User/Group=root，进入原 Q2 controller；一般 subprocess 的 close_fds 不构成 NS2 launcher 资格 | 尚无 NS2 普通监督入口、仅继承 stdio 的准确封闭 launcher/source pin、有限 FD 继承关闭表和其适用证据。旧 root controller 不能自动获得新 collector 用途 |
| aggregate RAM ≤128 MiB、CPU ≤5s、3 新单线程任务、24/72 FD | [Q2 preparation](Q2_FIXTURE_PREPARATION_VERIFICATION.md#L35)是 600s/512 MiB/64 tasks/100% CPU；[validate_system_geometry](../../tests/e3_host/q2_supervisor.py#L208)固定 controller 512 MiB/64、ordinary parent 256 MiB/32 | 原对象限额与 NS2 不同；尚无对 G/R/O 全域及收尾的准确 enforcement、计量与增量成本证明。配置中出现 CPUQuota/LimitCPU、记录 wait4 RSS 或一般测试能结束，均不足以绑定本合同整体上限 |
| 原 30s 双钟、20+5+5 阶段、真实 stop/wait/EOF | [verify_installed launcher](../../tools/verify_installed.py#L57)是 MONOTONIC 90s、每流 32 MiB及自身 drain/join 合同；Q2 的历史原停止缺项如上 | 尚无 NS2 已有树外普通监督对原 G 身份、全域停止、G 原退出与 stdout/stderr EOF 的适用证明和准确有界 receipt；不能用另一条测试的 kill/EOF 或 pytest 退出替代 |
| N09 本地双钟/暂停 fixture | A 明确 N09 的暂停语义只在已 supplied clock fixture 上验证 | 已查材料未定位被提供的暂停 fixture、source/接口适用记录与有界监督条件。没有把 H07 跨机时钟/首次远端 fence 要求移入 NS2；此处只是 NS2 本地暂停条件 |
| 原生 audit、外部监督/收件增量费用 | 有 CI 原始日志留存与旧来源/容量审阅；[原回传](evidence/q2-readonly-return-20260927/manifest.json)保留其私有审计索引 | 这些审阅报告不是 namespace session 的原生日志、收件或监督费用界；尚无准确对象/设备/次数/上界/覆盖关系。collector 不创建文件不能推导 fixture/audit 成本为零 |
| 可复用现成设施及用途 | 原 H07 native spike 有历史反例/清理记录；[retirement](SYSTEMD_CANCELLATION_REPAIR.md#L15)为 RETIRED_UNQUALIFIED，[workflow](../../.github/workflows/q2-cgroup-fence-spike.yml#L30)为 `if: ${{ false }}` | 退休实验不是现成 NS2 fixture，不恢复 helper、实验账户或第三轮。旧 Q2 guest 的授权也不自动覆盖本 local-only standalone 用途 |

CPU 术语按一手接口核对：[systemd v257 resource-control](https://github.com/systemd/systemd/blob/v257/man/systemd.resource-control.xml#L224)
将 CPUQuota 定义为周期内 CPU 时间百分比；[Linux man-pages getrlimit(2)](https://man7.org/linux/man-pages/man2/getrlimit.2.html)
的 RLIMIT_CPU 是进程 CPU 时间界。它们本身不是三端合计 ≤5s 的证据。这里仅核对
术语和论证范围，不将 v257 或 man-pages 版本采用为历史 guest/当前机器的实际构建。

准确 CI 的原始私有日志仍保留，其索引已有 bytes/SHA。该日志第 812 行的真实 systemd/cgroup
integration 为 SKIP：缺 predelegated manager admission / `E3_SUPERVISION_UNVERIFIED`；
第 681 行的 root collector 和第 1082 行的 installed wheel 属各自限定范围。
[真实集成测试](../../tests/test_local_hand_jobs_runner.py#L1264)和
[collector 限定](../../tests/test_e3_q2_reconciliation_collect.py#L1)不将这些结果升格为 NS2监督资格。
原件内容、机器路径、身份与命令不复制到 Public。

## 环境准备与后续实施分开判定

应先从已持原件静态绑定：选定 fixture、已有 runtime/普通 launcher、独立监督的
原身份与资源/停止/EOF界、原生审计/收件增量费用、暂停 fixture 的来源和适用性。
这一步不要求先获得 collector 成功报告，不形成“必须实现后才能确认环境”的循环。
准确 collector D、最终 artifact/context/session 以及 N01–N12 的动态资格属于后续实施结果；
须在 Owner B 与独立 CLOSED C 后形成，不能在 OPEN 下先实现或运行探针来填本表。

已查范围为仓库文档/索引、现有 source/workflow 和已保留的开发/CI 输出；没有枚举整台机器、
访问 guest、SSH、proc/status/nsfd、执行新 collector/test/probe、provision、修改系统或恢复退休设施。
本结论不要求 Owner 重找已留存的 Q1/Q2 原件，只指出尚未形成的 NS2 适用绑定。
若已存材料不能提供所需能力，而确需新增设施或改变来源/权限/监督合同，应先形成准确
受影响方案和文档，再按 R 决定；当前 A 不含临时补建这类设施的授权。

本审计不建议把“批准 A”解释为 NS2 已 READY；按当前输入，native 资格继续 BLOCKED。
原三文档/既有 CLOSED 范围及全部历史失败保持，当前无本提案 Owner B/C，
`field_ready=false`、`allow_run=false`、`guest_executed=false`、真实正常链计数 0。
脱敏出处/源码摘要和分层状态在[复核索引](evidence/q2-namespace-fixture-20261002/review.json)。

## 后继候选状态（2026-10-03）

本复核针对的旧 scope `LH-Q2-NAMESPACE-REFERENCE-v1` 与 proposed A `dfdd653…` 现登记为
`SUPERSEDED_PROPOSAL_NOT_APPROVED`；上述只读观察、来源和限定结论继续按审计时点保留，不回写成
后继候选的当前现场事实，也不追认旧 Owner B/C。

后继 `LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1` 的准确 proposed A
`ad5abaee642cba02d997149badf75a08c219a35c` 见
[新基线登记](../governance/Q2_NAMESPACE_FIXTURE_DELIVERY_BASELINE.md)。新候选把离线 plan、既有 sealed
watchdog W 的严格静态资格、实现/合成验证、一次 conditional guest delivery、最多十二个 native case
和最终收件列入同一 F0–F4 提案；它仍不授权安装 W、补建环境、连接 guest 或执行现场任务。缺 W 或
其它固定输入时仍须 `NOT_ISSUED`/BLOCKED，不得把本复核升级为 readiness PASS。新候选同样 Gate OPEN，
尚无 Owner B、CLOSED C、implementation D 或 live run。
