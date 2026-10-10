# PP1–PP3 一次原核心接续

**PROPOSED / Gate OPEN / NOT APPROVED**；`LH-Q2-CORE-PERSISTENT-PATH-CONTINUATION-v1`。
仅实现[需求](REQUIREMENTS.md)及[架构](ARCHITECTURE.md)。无独立诊断/观察交付。

1. 本 A 只增加三文档。Owner 对准确 R/A、PP1–PP3、正常 PR 合入及私有固定出站
   范围一次决定；独立 C 只登记 CLOSED，D 必须下降自 C，不 squash。当前一般核心
   进展指令不补写成不存在的新 A 的批准。旧 A/B/C/D、freeze、失败终态保持。
2. 获批后将 PR #4 准确 head `47183cc310cbab15cf78bdb8f3f26cc935c1fb66` 转 ready，
   复核同一 head 检查后正常 merge commit 合入；不使用管理员 override 或直接推送
   main。本批 A/C/D 也通过正常 PR 流程交付并保留历史；发生新的审批拒绝即停止该
   动作，不能换入口执行。原 PR #4 检查不替代后续准确 D 自己的首次 CI。
3. PP1 修改 `q2_core_prior_attempt` 的固定归档读取/历史重建，维护 host 的输入和
   source binding，delivery contract、capacity、approved-input、transition 和两个
   独立消费者的授权/版本/费用。采用 PR #4 已验证分类，保留旧 source 比较及保护根。
   不修改 guest 缺失拒绝或扩大 runtime preparation；必要拆分须仍在原 source/bundle
   预算内。无新依赖、通用扫描器、平台或生产迁移。
4. 从原冻结 callers 准备两个独立新 caller，旧文件不改。一个仅执行新 10d 维护，
   一个只在完整维护通过后发行原未发行 07a。接齐实际 result/summary 的 diagnostic、
   create-only 消费、实际顶层/子进程完成、EOF 和终态，不用摘要自报替代原件。
5. 用固定已留原件核对外层 12 成员/522240 B、内层原 bytes/hash、旧两归档与 55
   原件、10c 五件/缺件/退出事实、两次读取原件与旧冻结。不得再调查旧故障或读 VM。
   验证历史引用损坏、来源替换、重复/遗漏/循环、旧失败误作成功和版本不匹配均拒绝。
   producer 与两个独立消费者分别覆盖 canonical 还原，不复用 producer 自述作验收。
6. 保留真实受保护文件 opening/holding/recheck、真实隔离 pre/post 管道、普通子进程
   PID/start 绑定及完整 128-FD 生命周期；仅以合成 peer 替换现场效应。覆盖原缺失
   必备证据、权限/名称/内容漂移、FD admission、计量失败、传输/EOF/完成失败，验证
   catch/finally 和实际持久化路径。不得模拟掉已发生过故障的真实本地文件边界。
7. 重新核算十六份维护义务、旧读取和准备费用、两个新准备池、原核心，合计
   20809 MiB / 6224 inodes；保持各阶段原 clock/limits。以新准确绑定及允许的最大
   返回验证所有源、归档、manifest、receipt、payload、argv、transition、approved-input
   和核心包上界，以及父/子聚合 FD/CPU/RSS/进程成本，超界停止。
8. 必要代码及脱敏记录正常发布 main；准确 D 自己首次 CI 三项成功，Linux/Windows
   CI 独立安装及本地独立安装完成。保存早期失败，不能用 rerun 代替首次记录。完成
   最终受保护来源准备，冻结两个新 caller、全部依赖/输入、准确批准和固定出站槽。
   当前固定尺寸不替代本步骤；PP1 完成前不能接触新维护现场。
9. PP2 只一次新 10d preflight，PASS 才同窗 execute。只允许原固定最多两次 SSH、
   核验后的正常关机、原 journal 增长、原配置一次维护重启和原限额 runtime preparation。
   不增加前置 guest 读取或探测。保留 marker、实际捕获和完成；失败立即停止。
10. 只有完整成功维护原件及两个独立消费者通过、实际 coordinator/custodian 完成，
    PP3 才直接发行原 07a H01→Q4→H11 并收回结果。批内无需逐项审批。最终只更新
    现有核心状态及必要脱敏记录，逐案报告 PASS/FAILED/NOT_RUN；不能以 CI 或文档
    代替核心验收。失败无新重试、补采、清理、回滚、恢复、启动或窗口。

当前仅有三文档和固定原件的只读核算；新归档文件、实现、调用器均未生成，PP2
NOT_ISSUED，PP3/H01/Q4/H11 NOT_RUN。批准前继续保留 PR #4 和所有旧失败，不执行
被拒绝的 main 推送，也不改用 PR merge API 绕过该拒绝。
