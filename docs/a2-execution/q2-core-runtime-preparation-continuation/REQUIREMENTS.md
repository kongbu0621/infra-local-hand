# 运行准备修复后的原核心接续

2026-10-11；Authority：Owner；**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-RUNTIME-PREPARATION-CONTINUATION-v1`，RP1–RP3。
R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；直接规则来源及完整性、Owner mandate、
Owner-only closure、无例外及实质变更控制保持，见根 AGENTS.md。

## 唯一交付与当前事实

交付仍为原未发行 `lhqcore-20261007a`：H01 执行并取回结果 → Q4 运行中取消 → H11
同任务恢复查询。NAS 发现、提交及参数展示已关闭；外围扩展、新插件/连接器、扫描器、
诊断平台及无关重构继续暂停。历史任务查询和取消保留。

IR1 已完成。唯一 `lhqjgrow-20261011a` 在 `PRE_RUNTIME_PREPARATION /
GROWTH_RUNTIME_LIMITS` 停止：一条 pre SSH，五个实际原件；caller/coordinator 3、
custodian 0，remote_exit UNKNOWN。没有关机、备份、journal 增长、维护重启或核心包。
十五代维护已消费；旧09c/10b仍是调用过但未消费的 preflight；十七份完整义务保留。
IR2 CONSUMED_FAILED；IR3/H01/Q4/H11 NOT_RUN。

PR #14 的普通修复 `3b3163bdd4ae1f10a71ab9721a3647e54a8651bb` 已正常合入，首次 CI
`38075262477` 三项成功：只在两个固定目标的配置已确认缺失时，允许准确的空、inactive/
dead、默认 infinity 形状进入原配置创建流程；后续有效限制、身份和冲突检查不变。
PR #15 已补齐外围入口屏蔽；当前 main `2105772cf9d677e25acf4ab6562cfd408f5b6f2b`。
这些发布不恢复已消费窗口。实际返回见[现场记录](../Q2_CORE_IDENTITY_RESOURCE_FIELD_20261011.md)。

## 待一次决定的范围

1. **RP1**：采用已发布的运行准备修复，接入旧11a实际原件、完整完成记录、历史和成本；
   完成生产者及独立消费者、正常 PR 发布、准确 D 首次 CI、两平台及本地独立安装、
   全生命周期/载荷/资源验证和新调用器冻结。旧调用器、冻结和终态字节不变。
2. **RP2**：唯一新 `lhqjgrow-20261011b`，一次本地 preflight，PASS 才同窗 execute；
   至多两次固定维护 SSH、一次验证后的正常关机、原备份及 journal 256→512 MiB 增长、
   一次原配置维护重启及 post 验证。每 boot 沿用最多12个准备命令/120秒，计入原总窗。
3. **RP3**：仅完整维护成功原件、实际 caller/coordinator/custodian 成功完成、必要 EOF
   和两个独立消费者均通过后，发行原07a，沿原一次连接完成 H01→Q4→H11，逐案报告。

Owner 的整批决定须明确准确 R/A、RP1–RP3，以及私有请求列明的原 Q1 固定目的地和
维护源码/目标路径身份元数据、条件核心包的出站授权。实现、验证、正常合入、冻结及
范围内执行不逐项再审批。私钥/凭据内容不发送；无其他接收方或预探测连接。

## 固定边界及费用

采用当前四个 source-bound quota 叶对象策略和档位2；保持祖先及写位检查、178必备
路径、230保护根、Q1、19/7/7、domain/cgroup、进程/写入者/数据保护、原 VM/install 和
trusted-single-admin/declared-startup 前提。不修改原核心任务参数、journal目标或内核
单参数边界。关机改变易失状态和 boot；备份后增长不原子，仍遵守失败即保留。

保留十六代各1296 MiB/370 inodes/CPU120秒及旧11a的2200 MiB/402 inodes/CPU240秒。
新11b另占2200 MiB/402 inodes/CPU240秒，共十八份完整维护义务。旧11a已计入的904 MiB/
32 inode余量保留，新11b余量只在它自己的2200 MiB/402内计一次，不再附加全局余量，
也不重算更早十六代。历史读取与准备共15 MiB/480 inodes全部保留；新增来源及归档准备
各2 MiB/64 inodes，原核心捕获128 MiB/32 inodes保持。

合计 **25283 MiB / 7364 inodes**；维护准入 **25155 MiB / 7332 inodes**。
无退款；当前23079 MiB/6834 inodes仍是旧已批准义务，此处新增费用仅为待批准方案。
维护当前CPU240秒、聚合RSS1024 MiB、每进程AS512 MiB/FD256、总窗1800秒/变更截止
1560秒保持；两个新准备池各CPU/wall240秒、聚合RSS1024 MiB、AS512 MiB/FD256。
旧CPU、guest成本及核心当前承载限制保持，不再提高执行/传输/捕获上限。

未知、矛盾或失败立即停止保留；无旧重放、新retry、补采、业务停服、清理、回滚、
额外恢复/启动/窗口或外围工作。H11仅为原同任务。raw、索引、归档、caller和机器资料
保持私有；必要文档/实现/脱敏记录经正常PR merge commit，不直接push main或越权合并。

RP1 NOT_STARTED、RP2 NOT_ISSUED、RP3/H01/Q4/H11 NOT_RUN；本提案不是现场授权或PASS。
