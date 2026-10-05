# 核心容量单次观察实施计划

状态 **PROPOSED / Gate OPEN / NOT APPROVED**。Scope `LH-Q2-CORE-CAPACITY-OBSERVATION-v1`，仅 O1–O3。
服从[需求](REQUIREMENTS.md)和[架构](ARCHITECTURE.md)；支线保持暂停。

## 准确 A 与授权顺序

本三文件形成仅文档 A，再独立登记 A commit/tree/三文件摘要和 OPEN 状态。
既有“推进核心功能”、截图、05c CLOSED 或诊断修复不被转写为本次准确 A 的 Owner B。
Owner 基于准确 A 批准后，逐字保留 B、Owner、时间/稳定事件来源、R/A/scope；另作仅 bookkeeping
的 CLOSED C，不能混入源码、测试、配置或发行摘要。新实现 D 从 C 后继，不 squash C 与 D。
所有未受影响的既有 CLOSED 权限保持；本次 A 在批准前没有可执行原型或新测试。

## O1 实现一次容量观察

在 `tests/e3_host` 增加本范围 reader/runner 和窄测试，复用现有稳定读取/捕获原则。
不得复用已消费 run 入口，不改 release allowlist、bootstrap、dispatcher 的准入谓词或业务 runtime。
实现固定 plan/路径、管理 pins、全额承诺、一次性状态机和受保护四件回收；随后实现五目录观察
和纯本地条件计算。无需重新安装、cloud-init、生成完整 core package 或建立新业务 unit。
新代码只能在本范围 CLOSED 后编写；遇到需改变固定对象、预算、信任或合同的事实，停止并按 R 审阅。

## O2 窄验证、准确冻结与本地交接

只验证本次具体风险，不重跑无关专项或全套矩阵：

- 固定 plan 摘要/长度、五个映射、描述严格语法及输入摘要；不依赖未保存的完整 05c package。
- no-follow、祖先/最终 owner/mode、O_NOATIME、路径替换/overmount、fd/mountid/dev/UUID 不一致，
  非 ext4/root/rw、边界长度/数量、proc 短读/超限；临时合成 fixture，不向真实 guest 借环境补测。
- 使用 f_bavail/f_favail，负值、等号、bytes/inodes 单独不足、同池最小值；全部 15 分组与原
  固定容量分量相符，四旧批全额、配置配额全额、共享义务去重，无第五批或退款。
- 预检失败零 marker/连接，并发仅一 winner、已有/部分文件、同步失败、双流超限、EOF 缺失、
  exit 非零、格式/摘要不符、原时钟耗尽、无法 wait；任何 marker 后失败零重试。
- 假 transport 核验固定 SSH/remote argv、空 stdin、60s/55s、reader 限制、只停止自己的子进程；
  禁止额外 SSH、业务/helper/目录遍历调用。此类验证不是实机 PASS；受限环境如实 SKIP/BLOCKED。

准确 D 干净提交并记录 reader/runner/参数摘要、窄测试结果、`git diff --check`。
等待准确 D 通常触发的相关 CI，失败先修；不为纯文档登记重复全套测试。
按架构仅本地核验已有计划、六个固定档案的固定容量分量、管理 pins、原 capture 索引；
生成五路径描述及全部 15 分组门槛表。不得探索其它档案或重放已完成的 sshd 解析。
失败不创建 marker、不试 SSH。准确执行清单只在本地内存，绑定 R/A/B/C/D 和输入摘要；
摘要随 O3 固定 marker/receipt 保存，不另生成新业务 ZIP 或现场文件。

## O3 单次观察与可行动结论

在准确 B/C/D 和 O2 通过后，既有物理管理端本地 Codex 执行一次 `lhqcap-20261006a`；
同一 60s 窗口重新完成必要本地身份和 264 MiB/80 条件检查，再创建永久消费 marker 后连接。
仅观察五目录并回收固定四件；预算全部按需求，不延长旧窗口、不执行 H01/Q4/H11。
返回完整私有证据后仅一次 ≤5s 本地计算，输出每个实际池的可用量、原合同门槛及两种缺口。

报告必须明确：当前观察时间、准确 D、请求数、消费与完整性、角色分组、条件假设、未验证的
历史 placement/配额/远端闭合。若失败则保留原字节和可完成 receipt，说明首个实际条件；
不追加连接、补采、清理或新批次。若当前足额也不能将这次观察改记核心成功。

交付源码/窄验证记录、准确 D、私有 capture 摘要索引、脱敏容量表和一个针对实际缺口的修复建议。
真实扩容、删除、配额/资源合同修改或下一次业务验收均不在此范围；没有缺口则报告原失败值仍未知，
不凭当前数据否定历史失败。保持原安装和全部原件；生产 E3 与所有支线状态不变。

## 本地 Codex 交接

拿到这组三文档后先核对 main 和本范围 baseline。OPEN 时只审阅，不创建新 reader/runner 或连接。
准确 Owner B 与独立 C 后，直接完成 O1→O2→条件 O3；同一批准范围内不逐项重新询问。
此轮交付点就是一张实际容量/缺口表，不能转回 namespace/watchdog、审计平台或通用重构。
