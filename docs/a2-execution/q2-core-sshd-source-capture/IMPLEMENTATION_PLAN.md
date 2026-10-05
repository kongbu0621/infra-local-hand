# sshd 配置单次只读取证实施方案

状态 **PROPOSED / Gate OPEN / NOT APPROVED**。Scope `LH-Q2-CORE-SSHD-SOURCE-CAPTURE-v1`，仅 P1–P3。
本方案服从[需求](REQUIREMENTS.md)和[架构](ARCHITECTURE.md)；原 R、Owner authority、无例外及独立 C 规则不变。
目标是补齐核心故障输入，不是新验收平台。预算、对象和失败规则不在实施时临时选择。

## 准确批准和独立登记

先提交只有三份提案文档的准确 A，再独立登记 A commit/tree 和三文件 SHA-256，根 AGENTS 标记该范围 OPEN。
只有 Owner 对准确 A 的明确决定才构成 B；截图要求准备、CI success 或原 05b B 均不能替代新 B。
收到 B 后保存逐字决定、Owner、稳定事件来源、R/A/scope，再作单独 bookkeeping-only CLOSED C，不夹入实现、测试、配置或发行摘要。
新 D 必须从 C 后继，不能 squash C 与 D。若需要改变固定输入、信任、预算或一次性规则，按 R 重新审阅，不扩大实现解释。

## P1 固定只读取证实现

在 `tests/e3_host` 内新增本范围专用 host runner 与 guest reader，以及对应窄回归；复用既有稳定读取/身份校验原则。
先完成 source/argv 固定、旧核心入口隔离和一次性状态机，再接数据读取与私有回收。禁止以原业务 carrier 试跑新诊断。
reader 不写 guest 文件、不启动子进程、不运行 sshd/sudo helper 枚举、不调用核心安装/执行/恢复方法。
冻结的数据 closure、元数据复核、受保护 capture、两个流的独立限额以及无法完成时的 UNKNOWN 处理必须实现齐全。
新代码只能在新 Gate CLOSED 后编写，本 A 不包含 executable prototype。

## P2 离线验证和条件发行

不需要再跑无关全量验收矩阵。先做下列针对性验证，任何失败均不消费现场连接：

- 人工临时 fixture 覆盖主文件、可缺目录、多个 `.conf`、非选中项、目录/文件边界；验证原 bytes 完整和顺序，覆盖非 ASCII 文本与当前拒绝文法作为数据返回。
- 故障覆盖 symlink/hardlink、父目录保护、特殊文件、O_NOATIME 拒绝、fd/name/内容/目录漂移、文件和目录数量/长度超限，无 fallback。
- 状态机覆盖预检失败零 marker/零请求、并发竞争仅一 winner、部分 marker、输出名已存在、marker/目录同步失败、三个输出创建失败；任何 marker 后失败均零重试。
- 注入短读/短写、非 UTF-8/重复 key/额外 JSON、base64/摘要/身份不符、双流超限、EOF 缺失、非零 exit、时钟耗尽和无法 wait，确保不能产生成功记录或第二请求。
- 用本地假 transport 验证精确 argv、禁用项、空 stdin、60s 原起点/55s 停止点及只能信号自己的子进程；这不是现场 PASS。
- 在受控本地临时 fixture 验证 reader 的限额设置和失败路径；权限不足项明确 SKIP/BLOCKED，不记 PASS，不向真实 guest 借环境补测。
- 检查零业务调用、零核心 allowlist 变更、无秘密/原配置外泄、无第三方依赖，以及 source/argv/capture 全部固定上限。

准确 D 必须干净提交，保留窄测试的命令、结果、必要 skip 原因、`git diff --check`、源码与参数摘要。
发布通常触发的 CI 如实报告，CI 不是现场证据；不因文档变更反复重跑全套。任何影响本方案的相关 CI 失败未解决前不发行。
本地验证仅使用已知 anchor 的必要材料，不再遍历旧证据档案。原管理 pins、私钥关联、SSH 选项支持和 writer 保护任何不符均 BLOCKED。
本地预检不得执行 wrapper、试 SSH、创建 marker 或写新现场 capture。
准确执行清单只在本地内存中生成，绑定 R/A/B/C/D、reader/runner/argv 摘要及固定对象；必要摘要随 P3 固定 marker/receipt 保存，不新增现场文件或业务 package。
准确 D 和私有清单通过后，同范围内不再向 Owner 逐项询问；P3 仍须再次通过同窗口本地预检。

## P3 条件单次采集和离线结论

只允许 `lhqsshd-20261005a` 一次 marker 和一次固定 SSH exec request；同窗口核验准入、建立 marker 后才发送。
60s caller、20s reader、5 CPU-s reader、128 MiB address-space、65 文件/1 MiB、2 MiB stdout、64 KiB stderr、4 MiB/8 capture 与 196 MiB/56 当前容量条件全部按需求实施。
完整结果只保存在受保护本地。返回后只作本地 schema/hash/来源校验；取证窗口结束后最多一次双解析器对照，各最多 5s，不追加连接核实现场。
若失败或不完整，保留原字节与能写成的 receipt，明确请求是否发送、消费是否发生、快照完整性及 UNKNOWN，不清理、不补采。
若成功，报告确切当前拒绝条件、文件序号/行号/摘要及其与 05b 历史的证据差距；原文不公开。

交付源码/窄测试记录、准确 D、私有 capture 索引和脱敏诊断报告。取证成功不关闭 H01/Q4/H11，不启用生产 E3，不自动授权改文法或第四次核心验收。
如果根因需改变既有固定准入合同，先提交相应最小 A；若只是既有 CLOSED 范围缺陷，按原规则另作精确修复和验证。
现场后无下一批、无自动 retry、无重连、无业务执行或清理；支线保持暂停。
