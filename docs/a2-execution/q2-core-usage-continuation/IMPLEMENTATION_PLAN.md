# UC1–UC3 落地顺序

**PROPOSED / Gate OPEN / NOT APPROVED**，`LH-Q2-CORE-USAGE-CONTINUATION-v1`。
本计划落实[需求](REQUIREMENTS.md)与[架构](ARCHITECTURE.md)，R 与现有采用规则不变。

1. A 仅提交这三份文档。Owner 基于准确 A、原 R 和 UC1–UC3 作出真实 B；独立 C 只登记
   CLOSED/决定/经批准最小索引，随后实现 D 从 C 下降，不 squash。当前普通修复属于旧
   FD1 的计量修复，不代表新 UC 已获准。
2. UC1 先核验九份保留来源与六文件索引，创建独立私有归档和固定输入声明，保留原件、
   原 caller/freeze/gate。新 private gate 在完整验收前保持 NOT_READY，不导入旧 caller 执行。
3. 在既有 `q2_journal_growth.py`、`q2_core_prior_attempt.py`、delivery contract、
   approved-input、独立 dispatcher、entry/freeze 内完成 UC 来源、私有本地失败保留、
   新10a session、版本与十三代成本接线；guest 只采用精确新 session/来源，业务和保护不变。
   更新所有准确来源摘要。私有维护/核心 caller 与独立验收器必须同步完成，不留旧入口。
4. 离线验证必须覆盖：普通控制进程真实退出计量；旧本地失败真实归档/索引/冻结关系；
   缺项、错摘要、错 D、假终态及版本混用拒绝；实际 guest 报告经过两个独立消费者；
   真实128 FD、AS256 MiB下增加一个父输入的完整生命周期；原CPU/RSS/进程/IPC限制；
   准确全部历史、完整 marker/receipt/bundle/argv/transition/approved-input/整包大小。
   测试只用保留来源和隔离 fixture，不查询现场。静态超界先修复，不扩大上限。
5. 发布准确 D 到 main，核验其首次 CI 全部成功及独立干净安装验收，固定全部输入与两份
   caller，保存不可变 freeze。既有失败 CI 不覆盖、不重跑冒充首次通过。完成这些才允许 UC2。
6. UC2 的唯一 caller 先 create-only 登记调用；一次 preflight 失败即停，不 refund。
   通过后只进行同窗 execute，不重置原时钟/累计用量。沿用原 VM/安装、维护动作与最少
   SSH；保存五件维护原始返回、原索引和真实顶层完成，不把 UNKNOWN 写成成功。
7. 只有独立验证完整维护成功后，UC3 才以新 VM/boot/已验证维护转换准备并执行原07a
   H01→Q4→H11。一次批次、原预算，任一失败停止；不补跑、不额外恢复或另开窗口。
8. 保存新证据与旧原件、原 frozen caller 和全部失败。仅发布已批准的脱敏结果；明确记录
   各阶段 NOT_RUN/FAILED/PASS 与实际次数。新10a原文/索引保持私有。

完成定义是原核心三个案例及结果收集真实通过；代码、CI、安装或维护某一层通过均不能
代替它。当前 UC1 NOT_STARTED、UC2 NOT_ISSUED、UC3/H01/Q4/H11 NOT_RUN。
批准后按本批次连续完成，范围内不逐步索取批准；超范围变化遵守 R，失败不自动申请下一窗。
