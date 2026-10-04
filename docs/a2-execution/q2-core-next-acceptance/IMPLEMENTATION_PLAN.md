# 核心下一次验收：实施方案

- Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
- Scope `LH-Q2-CORE-NEXT-ACCEPTANCE-v1`，仅N1–N3。R与来源完整性沿用[需求](REQUIREMENTS.md)。
- 顺序为准确三文档A → Owner决定B → 独立bookkeeping CLOSED C → 实现D；历史四条修订与原核心C均保留。
  A/B/C未齐前只允许文档与既有源码只读验证，不实现新批次。

## N1：同一核心链中的准确续验实现

1. 在 `q2_core_delivery_contract.py` 固定需求表全部新身份与本A/B/C来源；
   `q2_core_delivery_entry.py`、`q2_core_delivery_bootstrap.py`、`q2_core_delivery_dispatcher.py`
   同步carrier/session/路径/UUID/project/preparation派生。loader行为不变；不把旧marker另存为新marker。
   固定wire中的原scope/原manifest.amendment继续指原合同；新scope用于本次授权及新的UUID seed，
   来源冻结同时校验原所有C和本次C→D。新/旧对象不得出现混合组合。
2. `q2_core_approved_inputs.py` 从host受保护原件读取旧五文件，按架构逐字节核验、封装并独立消费。
   原义务prefix、历史nonissuance原件及云配置归一化不改写；不使用当前同路径文件冒充固定历史版本。
   freezer source-aware API与private ApprovedInputSources明确增加 prior文件输入，不设宽松缺省。
3. 既有 `_cap_charge` / admission source validation 同步接入旧core全额commitment；
   重算实际逐设备可用空间与host capture预算。记录承诺和观察值的区别；UNKNOWN不填零。
4. dispatcher在现有准入内添加架构的两次bounded只读unit/cgroup核对；
   只有CURRENT_SCOPE_QUIESCENT且原所有准入条件成立才进入create-only安装/后续任务。
   双端独立核验其原件摘要、旧boot/InvocationID/cgroup关联及当前观察，写入原admission member。
   新缺项/冲突走原STOP_AND_RETAIN，不进入owner/业务，不新增field module或后台程序。
5. freeze核验本准确A三文档、B、独立C与全部原授权链。release allowlist保持空至N2全部完成。
   原field cap不足或实际需要改变wire/预算/权限时停止受影响范围，不能静默扩张本A。

## N2：在消费机会前发现接线错误

必须覆盖以下实际失败模式，测试与fixture均明确真伪边界：

- host真实package builder/parser产生entry，贯穿HELLO/BIND、guest parse及marker规范回构；
  writer缺失/未知字段和不合法basename在host最早可验证位置拒绝，不消费现场机会。
- 用真实私有cloud-init、旧五原件和历史输入进行本地source-aware全链聚合；不得用替换pin样本代替此检查。
- 旧文件误选、摘要/身份不符、缺件、原stdout不止一个完整HELLO、package/BIND非零或原状态被改写均拒绝。
- loaded同Invocation terminal且空scope、not-found且两次原cgroup absence为两类正例；
  active/populated、同名新Invocation、boot变化、父替换/alias、截断/超时/晚返回均停止。
  not-found正例不得输出historical exit PASS或usage=0；没有旧PID starttime的样本不得仅靠PID通过。
- 旧全额commitment加新commitment后的容量不足必须拒绝；保留更早历史prefix，不退款/不覆盖。
- 新UUID/21project IDs/所有controller与lhj派生unit互不复用旧对象；未知替代名不接收。
- H01结果、Q4 RUNNING取消、H11自身ledger恢复及全部82成员消费继续用原语义；模拟不冒充现场PASS。

冻结准确D后运行定向、完整源码和独立installed verifier，并核对CI准确SHA。
测试wheel不替代现场wheel。先离线完成source/template交叉审查，再在同一原900s live caller窗口内
取得真实held anchor/writer/原件，完成两次独立包构造/解析、原输出absence及新release gate。
不能复用结束caller的writer/window；不同一次只读准备检查不授予任何现场请求。
准确release digest只登记在所有原及新增条件通过之后；新批次对象实际不存在仍由原live caller核对。

## N3：唯一新请求与交付

本地Codex持有真实私有材料，负责按准确D运行原管理入口；云端实现/审查不代替本地观察。
只发需求表指定的一次carrier，在其准入内核对旧scope。失败即保留，不另开退出检查连接。
通过后原H01→Q4→H11顺序执行；前一case未完整PASS不提交下一case。
既有SSH/管理配置复用，既有安装、unit、quota、marker与证据不删除、不重装、不改权限。
不因收不到结果而执行第二次业务；H11只恢复其自身origin而不读取业务结果补统计。

完整返回须独立验证原session、请求、identity、case verdict、资源与退出证据。
报告列出准确D/tree、包SHA/bytes、消费状态与三个case实际结果，原UNKNOWN单独保留。
原生产E3与支线限制不变。失败时保留明确缺项，不能自动进入第三批或另一个资格测试项目。
