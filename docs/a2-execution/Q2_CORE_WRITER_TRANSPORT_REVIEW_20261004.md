# 核心 writer 传输修订：实现与验证

2026-10-04。本件是 `LH-Q2-CORE-WRITER-TRANSPORT-v1` T1–T3 的局部交付记录，
不是完整 D1–D4、现场验收或新的 F1。

## 准确来源与实现

R 保持 `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，已直接读取固定原件。
A 为 `60756caedf6a2d978627272e44784d11009ac309`，三份文档与历史 OPEN 标签字节未改。
[Owner 原文 B](../governance/Q2_CORE_WRITER_TRANSPORT_OWNER_DECISION.md)保存在独立 bookkeeping-only C
`8e891e11fb6e563353013ac94c201f30a1df66c9`，tree `2c2ae6e075176ca359d411c127267ea1a959ddce`。
C 只包含 AGENTS 登记和决定副本，没有 source/test/schema 实现。

本次准确 D 为 `0e72ffae85f247e9423ef2cfa9bda26cf8ba6077`，
tree `bf9cde9cdd759f5cc055d5896147d7d2aacdb947`，direct parent 是上述 C。
它也继承原修订 C `7598886e15ed6911fe0e09e2f8d66203455f9057`。
实际 `_implementation_blobs` 已对该 D 验证两套 A/B/C 的 tree、祖先关系、A 文档和 B 原文摘要，
并从准确 Git blob 读取 field 源码；未从工作树或旧 D 冒充新代码。

| Field blob | 字节数 / 原上限 | SHA-256 |
| --- | --- | --- |
| loader | 2160 / 8192 | `6cf45d3888e33aa386dacba5411635240c8c8e8585df01844657aedd89fa9c61` |
| bootstrap | 49102 / 49152 | `2d8bed925e90cdb1992f3746aec92581957fdfa722fbdacda2d222a4b2544768` |
| dispatcher | 201515 / 262144 | `ff8338230357304b4126b7391faf522c77c94589b7b812dcd6141aacddbf626b` |

## T1：已实现

- strict package v3，顶层不变；entry 只增加原 held binding 的 writer，canonical no-LF ≤4096 B。
  缺键、额外键、旧 v1/v2、错误类型/范围、重复/乱序 groups 和超限均拒绝，不默认填值。
- freezer 复制同一个 writer，双序列化、host/standalone 双解析后再次逐 canonical bytes 比较。
  local-binding 摘要仍覆盖原完整 canonical+LF binding；delivery 在 marker 前拒绝 writer 替换。
- guest 从 manifest、entry.writer、BIND 原 clocks/package 重建原 marker v2，保留 16 KiB 限额，
  校验 consumption SHA 后派生 session 的准确长度/摘要。没有使用 guest writer 代替 host 身份。
- host 返回验证器独立重算 marker，核对本次真实 capture marker、BIND、session 和 held writer。
  真实 fsync/同 inode 回读、wait/EOF、六文件 finalizer 和原 deadline 不变。
- 新 A/B/C 只进入 offline source-lineage 校验；wire amendment 仍引用原 A/B/C，不新增 authority 字段。
  runtime candidate `4b6e4a7c403362358192086b88679e1326dcb2e1`、原 wheel/projection/harness 不变。

bootstrap 仅压缩 continuation 排版以留在原上限内。AST 差异复核除新 writer validator、
PACKAGE_SCHEMA、ENTRY_FIELDS 和 manifest 的 validator 调用外，无其它可执行语义变化。

## T2：验证边界

定向测试覆盖各 writer 负例、4096 B 精确边界、marker 原文/LF、clocks/package 漂移、
新旧 schema 混拼、host-marker/session 回传不匹配、双 C 来源链和 release 继续拒绝。
临时目录还实际完成一次 marker create/fsync/回读，与 guest 重建相等，第二次 O_EXCL 创建拒绝；
这只是本地隔离文件测试，不是管理 anchor、现场 marker 或业务执行。

首次新增负例运行有 41 项失败：测试捕获了另一个 import namespace 的 ContractError，且误把
DispatchError 当 ValueError。随后只修正准确异常类型，未放宽产品校验；该失败保留，不当作现场失败。
准确 D 的全部源码/测试字节在最终完整回归期间未改变：**4298 passed / 99 skipped，431.42s**。
本机报告 `lh-core-writer-source.7zI1Ot/results.xml`，SHA-256
`dcb6874a166e57e964ff98ef312e115b4980608d8562cfb6f4112dbf20ecc3d3`。
定向核心集在最后两个测试加入前为 385 passed / 8 skipped；新 writer 专门模块最终 71 passed。
本机 8 项 protected-fixture skip 及其它 skip 均不计为通过；没有为此 sudo 或变更系统配置。

从准确 D 新建隔离 clone/venv，离线 build/install 并运行现有 `verify_installed.py`：
**PASS，94 checks / 292 commands**。该安装是临时目录中的独立测试，使用的验证 wheel
不替换批准用于现场的固定 candidate/wheel，更不证明 E3 真实任务链。
本机原报告为 `lh-core-writer-installed.8K5eSH/acceptance/report.json`，SHA-256
`b18f1bdf6302a7f149740e9853690ca8b5dff9bbe77aab352005ee5c39549fdf`。
独立测试 wheel SHA-256 为 `58388f894e1fb7c82500f52eb2782b906488b7ee32042017fc1b9f0d4fe03916`，
仅作为本次 installed suite 的工件身份，不是现场批准 wheel 的新身份。
[准确 D 的 CI](https://github.com/kongbu0621/infra-local-hand/actions/runs/37185160537)记录时 Windows job
已成功，Ubuntu source job 仍在运行；这不声明 Windows 现场支持。
不把旧 CI、SKIP 或执行中状态当作 PASS。独立 parser 回归、安装验证和本 executor 自查不是独立
Reviewer 签核，独立审查及原 D4 其它门仍待完成，T2 不记为全部完成。

## T3 与直接剩余项

准确 D/tree、两套 C 来源链和三 field blob 已冻结。完整私有 package 仍为 **null / NOT_ISSUED**；
只完成合成 fixture 的双 build/parse，未进入真实 host 900 秒 origin，也没有重冻/重发现场包。
release allowlist 保持空，`releasable=false`；仅已解决的 host-writer protocol blocker 被移除。

剩余直接实现：current guest collector/policy/历史义务逐 pool 准入；安装 shared-pool accounting、
内部 I/O deadline 和执行身份；existing-account preparation 与 plan；H01、Q4、H11 真效果；
动态 phase facts 和完整 usage/peak。随后完成独立审查及原 D4，重新冻结最终集成 D，再在原
900 秒双时钟 origin 内绑定真实 held writer、构建/双解析准确私有包并复算原预算和 release digest。
这些是已 CLOSED 范围内的既有缺项，不需要重复批准相同 A，也不转入 namespace/watchdog。

本次现场 marker/request/H01/Q4/H11 均为 **0**。真实业务任务未执行，业务退出未确认，
业务结果和证据未收回；未观察的现场事实继续 UNKNOWN。本轮未消费原条件单次 F1，无第二 request、
重连、旧批次重放、deadline 延长或系统变更。生产 `E3_SUPERVISION_UNVERIFIED` 保持；
namespace/watchdog 暂停；capture 仍为原应用限额和实际 allocation 检查，
`full_filesystem_peak_proven=false`，没有恢复已撤销的共享 FS 全过程硬峰值承诺。
后续仍须按原规则检查真实 marker 存在性；任何既有或 partial marker 都阻断发行，不能据本记录退款。
