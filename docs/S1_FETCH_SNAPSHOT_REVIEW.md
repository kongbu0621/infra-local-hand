# S1 精确分支抓取与快照一致性复查

输入 main：`98de21f2318ff9c0c05ba4f01b890f2e4cde3971`。
精确代码候选：`17290e8cbebe5d4e9b590a284c27b68a60ad9217`；tree：`34cf67633aefe824c0bd0f17a113476889bead5f`。
Owner 再次要求检查并直接修复，延续“全部提交推送”和“不要走全量测试，走链路测试”的授权。
本轮修复 A03 既有 Git mailbox 的精确分支选择、目录树准入与 checkout 一致性，并复验 A05 交付及收据恢复链路。R/A、S1 范围、Task/Result v1 和八项动作保持原义。

## 已复现的问题

原实现执行 fetch 后读取 `origin/<branch>`。该本地跟踪引用是否更新，取决于 `remote.origin.fetch` 的映射；显式抓取成功不能证明这个引用代表刚抓取的提交。控制端和 Worker 的既有准入检查并未要求此映射必须存在。

| 边界 | 修复前实测结果 | 修复后结果 |
| --- | --- | --- |
| 跟踪引用过期，远端已有合法 Result | controller 等待超时，漏读结果 | 返回本次抓取提交中的合法 Result |
| 没有跟踪映射且跟踪引用不存在 | controller submit 报无效对象 | 正常提交，重复提交返回 already_present |
| 跟踪映射不存在，远端新增 Task | Worker 漏读 Task，CAS 未执行 | 执行 Task，发布 Result，收据一致 |
| 分支不存在，但远端有同名 tag | 同步未拒绝分支缺失，继续使用旧引用 | 明确抓取分支失败，停止本轮 |
| 同名 branch / tag 并存且跟踪映射不存在 | Worker 未读取预期分支的 Task | Task 执行并向精确分支发布 Result |
| 刚抓取的树有非法控制文件，而跟踪引用仍指向旧合法树 | 未检查到本次抓取树的非法符号链接 | 在 checkout 前拒绝该树 |

六个新用例在原实现上全部 FAIL，修复后全部 PASS；失败日志与真实退出码保留。没有把预期复现失败改写为产品 PASS。

## 修复行为及边界

- 抓取前沿用共享 branch 校验，fetch 明确请求 `refs/heads/<branch>`，不再允许 tag 代替分支。
- 使用命令级空 refmap，避免本次同步依赖已有 `remote.origin.fetch` 映射；不修改用户持久 Git 配置。
- fetch 成功后解析 `FETCH_HEAD` 为完整 commit SHA，校验其格式；目录树准入和 reset 使用同一个 SHA。
- controller 和 Worker 的推送目标均明确为 `HEAD:refs/heads/<branch>`，避免同名 tag 导致目标歧义。
- 保留既有 shallow fetch、blob 过滤、目录树与磁盘预算、禁止 lazy fetch 的树检查、远端白名单、运行绑定、hooks / filters 限制及单写者恢复约束。

抓取失败不会继续读取旧快照作为本次同步结果，也不会新建替代分支。既有 CLI 对普通 Git 抓取失败返回退出码 2；controller 错误对象标明 operation=wait、error_code=git_failed，属于等待操作失败，未生成或宣称任务执行失败的 Result。先前已执行的副作用仍需通过持久收据核对，不能因本次无法抓取而自动重放。

bootstrap 使用新建独立 clone，其跟踪引用由自身 clone 命令建立；本轮没有修改 bootstrap 或扩大部署范围。分支 SHA 绑定不代表远端之后不会变化，也不宣称一般线性一致性；它确保本轮准入与 checkout 针对同一抓取提交。

## 安装态失败与补充修复

首个候选 `fac9984413582668605071d38bffeb29406de330` 的安装态在 30 checks / 101 commands 后因恢复轮次仍存在 outbox 文件而 FAIL。该轮的源码、wheel、环境、完整日志和现场均保留，未改写为 PASS。

对独立复制现场的发布函数、处理流程与 CLI 进行 Python 级追踪，均能清理同内容 outbox。系统不支持本轮 strace/PTRACE 诊断；对应失败记录单独保留。原始失败未捕获底层 errno，因此不能断言与下面的可复现缺陷是同一次故障，也不能把首次失败简单当作已解释。

补充故障注入确认 Python 3.12 的 Path.glob 会抑制目录扫描 OSError，导致 Worker 把读取失败的 outbox 当成空队列：既可能继续执行新 Task，也可能未发布待发 Result 却正常结束。两个源码用例在修复前均 FAIL。改为显式目录遍历，读取失败返回 local_outbox_unreadable / indeterminate，阻止后续处理并保留原收据与 outbox；恢复读取后正常发布且不重复执行。真实空目录仍正常返回，JSON 文件匹配与排序保持原平台语义。

最终候选额外验证这两个源码节点和安装态扫描失败注入，并用另一套新建 checkout / build / runtime 重新完成整个相关安装链路。最终通过记录与首个 FAIL 独立保留；首次异常的具体底层原因仍未确定。

## 精确候选验证

使用新独立 checkout、新 build venv、新 runtime venv；构建 wheel、安装后在源码目录外通过 runtime Python `-I` 执行链路。既有目录、环境和证据均保留。

24 个指定源码节点包含本轮八个边界、上一轮九个中断恢复及隔离用例、投递确认丢失和配置分支准入节点。未运行全量 pytest。

| 精确提交验证 | 结果 | 耗时（秒） | 峰值 RSS（KiB） |
| --- | --- | ---: | ---: |
| 指定源码链路 | 24/24 PASS | 40.551 | 33404 |
| 编译 | PASS | 0.102 | 14080 |
| wheel 构建 | PASS | 0.856 | 25396 |
| 新 runtime 安装 | PASS | 0.554 | 41036 |
| 源码外安装态 CLI 链路 | 53 checks / 146 commands PASS | 125.357 | 54480 |

RSS 为 Linux wait4 ru_maxrss，不是同时运行的整棵进程树内存总和。

安装态在合成的两个独立 mailbox clone 中移除跟踪映射和引用，完成原有控制端 → Worker → Result → 收据 → Git → 控制端链路；旧任务隔离、原子写入失败、冲突恢复、确认丢失、结果尺寸回退和子进程超时清理继续通过。随后在 bare Git 创建与 branch 同名、指向初始空 mailbox 提交的 tag，新增 node.status Task 完成提交、执行和结果返回。最后只在该合成 bare Git 中删除测试分支，保留 tag 和缓存结果，分别确认 Worker 与 controller 拒绝继续。

独立审计使用删除前记录的分支 SHA 复核 Task / Result，不以同名 tag 代替已删除分支。检查两个 clone 的跟踪映射和引用仍为空，HEAD 均等于最后成功同步的分支提交；tag 仍指向初始提交且不含本轮 Task / Result。两次分支缺失拒绝均有退出码 2、空 stdout 和对应错误日志。

- 环境：云端 Linux x86_64 / overlay，Python 3.12.14、Git 2.51.1、pip 25.0.1；固定构建依赖版本清单保留。
- wheel SHA-256：`67d7dd2cc52b331a2b4c00d0847d04d2318d9e9bd5d19dedb3bb21ff1411c86d`。
- 核心包摘要：`fa59e5f7a5111af8aeaa7423be4829ed716065982d5c64e3e8269b01abb8a83d`。
- 核对 70 个 Git blob、23 个 payload 文件、29 个 wheel 成员、28 项 wheel RECORD、33 项安装 RECORD 哈希和 20 个缓存代码对象。
- 核对 16 个完成收据、Task / Result / provenance 和四份原始隔离文件。源码、wheel、安装内容和 Git 提交绑定一致。
- 产物审计阶段重算 289 条命令、578 份日志摘要，保留实际退出码、耗时及 RSS；发布和证据封装另有核对记录。
- 三份批准文档与 A `7246b850ffdc2709e359b09cac99f0fb88bda209` 字节一致；依赖和工作流保持不变。

提交使用 `[skip ci]` 遵守 Owner 的链路测试要求；未修改或禁用工作流，不宣称全量 CI PASS。云端合成验证不等同 GX10 / aarch64 / ext4 复验；Windows 仍为 DEFERRED / UNVERIFIED。未执行现役服务切换、S2 或 artifact-ledger A2，未添加许可证，未公开 SOP 历史或实机原始证据。
