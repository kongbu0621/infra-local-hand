# E1–E3 实现复查与修复记录

日期：2026-09-22。结论：**已修复本轮确认的边界缺陷；E1 尚有实现缺口，E3 未完成，不可部署。**
本记录补充[首轮验证](E1_E3_VERIFICATION.md)，不把首轮计数或实机结论沿用到新代码。

## 准确来源与范围

| 对象 | 身份 |
| --- | --- |
| 本轮起点 | `d500384fb008118e08eaf9c2141662d075444891` |
| 修复与产物源码 | `c8176b06792880507ff8fb3fb4b0786656713121` |
| 修复树 | `921d6d985dce8ac74b1576ccb9cc5e0170f22ef7` |
| 规则 R | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本轮重新读取直接固定来源 |
| 批准文档 A | `79f73faedcd9cde4164b0d1625782dae27db6c2f`；三份权威文档逐字节未变 |
| 独立开工登记 C | `367632126c1930983a06b1854f63789448633148`；仍为修复提交祖先 |

Owner 的既有 E1–E3 开工及继续修复、直接 main 发布授权保持；本轮没有新建分支或 PR，
没有修改 GX10、提交实机任务、切换服务或推进 E4–E6。本文随后单独提交，不充当 wheel 的源码身份。
实际 Connector/MCP/Plugin 接入权限仍独立于源代码发布。

## 已确认并修复的交界

| 交界 | 原问题与修复后的行为 |
| --- | --- |
| 权限与资源 | 新 reconcile ID 在落账/占容量前核对当前 profile 与 input grant；旧 ID 的合法重取保持幂等。补齐 archive 与其他作业根的交叉冲突及 broker/authority 控制根隔离 |
| 前置验收与来源 | 取消旧成功任务不得刷新 PASS 顺序/有效期；使用持久封存事件与原执行观察时间。已退役 profile 的历史结果不阻断其他作业恢复。prepared 顶层与 bindings 的来源字段冲突明确拒绝 |
| 启动、取消与恢复 | 已接受的 runner handle 在回执落账失败前就进入受控停止集合；只有确证未投递才允许 no-start。每个新执行意图清空旧阶段退出证明，恢复活动阶段也清除旧库残留证明 |
| 封存登记 | helper publication 必须完整并匹配当前 operation/reconcile；不能用当前 helper 给另一个已退出作业登记证据。保存当前 helper 的退出证明，错目标仍保留不明状态 |
| 证据存储与交付 | 使用账本登记清单读取目标作业及其 reconcile seal；未登记半写残留不阻塞旧证据，已登记丢件仍报错。封存源根和生成 ZIP 在摘要前核对身份；下载使用固定目录/文件描述符、create-only 发布及最终摘要复验 |
| 证据语义 | 外 seal 与 ZIP manifest 的 bindings、reconcile ID、前 seal 必须一致；各自 SHA 正确不能掩盖跨文件矛盾 |
| 输入读取 | exact inventory 不再忽略缓存/副本内额外 `.git` 内容，目录扫描错误明确失败。OAuth 发现/JWKS 请求禁用压缩并拒绝编码响应，读取按固定小块和总预算限制 |
| CLI 与 Plugin | handler 线程启动失败释放连接和并发槽，监听线程未启动也可清理。Plugin 身份文件拒绝 FIFO 与重复 JSON 键；提交、观察、取消及 reconcile 回包绑定原准确身份 |
| Windows 旧 S1 夹具 | 修复 3 处 LF/CRLF 字节假设、干净构建夹具的 Git 换行属性及 Windows bootstrap shell 选择；保留原检查目的，无新增跳过 |

各分工保留原版失败反例与修后定向日志。独立收束复审另外核对生产拒绝声明、
CLI 证据索引接线、当前阶段退出证明和封存目标绑定，9 项定向通过。
定向计数与全量存在重叠，不相加作为总验收数量。

## 准确候选验证

| 检查 | 实际结果与适用边界 |
| --- | --- |
| 云端 Linux 全量源码 | `503 passed, 3 skipped`；Python 3.12.14，`-W error`；单独干净 worktree，运行前后核对准确提交及工作树 |
| 编译与 shell | tools、tests、Plugin 的 compileall 通过；Linux bootstrap 语法通过 |
| wheel 与独立 Plugin | 构建通过；Plugin 13 个成员、逐成员摘要与来源核对通过，连接仍为 `UNCONFIGURED_E4_REQUIRED` |
| 基础安装态 S1 | 全新基础 venv；`94` 项检查、`292` 条命令通过；验收根位于隔离本地临时目录 |
| MCP 安装态 | 全新可选依赖 venv；哈希锁安装、pip check 通过；脱离源码路径的 21 项测试通过，含真实 loopback HTTP/SDK 路径 |
| 安装身份 | 两种安装的完整 39 文件 payload 摘要相同；broker/MCP 实际入口均通过准确来源校验；基础安装缺少 extra 时明确拒绝 |
| 批准链与差异 | A 三文档字节、C 祖先、工作树和 diff 检查通过；新增内容的私人路径/凭据模式检查未命中，范围有限，不作为任意秘密不存在的证明 |
| Windows CI，准确提交 | 完整 job 成功；源码 `179 passed, 120 skipped`，原 5 处失败消除；120 为原有平台跳过，未新增。平台限定安装态 `10` 项检查、`10` 条命令通过，另 8 项 Windows 专属检查全部成功；不证明新 Linux jobs/MCP/Plugin 的 Windows 支持 |
| Linux CI，准确提交 | 完整 job 成功；源码 `505 passed, 1 skipped`，安装态 `94` 项检查、`292` 条命令通过，Plugin 构建和 Linux repeat-bootstrap smoke 成功；没有触及 job 超时 |

本机 3 项跳过分别为两项 AF_UNIX 实际传输（宿主返回 EPERM）和一项真实 systemd/cgroup 集成。
第三项同时包含本轮明确的启动准备代码阻塞，不能全部归因于环境。
Linux CI 汇总为 505 通过、1 跳过，但日志未逐项输出该跳过原因；不靠总数猜测具体测试身份，也不据此解除生产启动准备阻塞。
真实七接口组合仍使用合成 manager/业务结果；生产工厂成功启动、受监督的真实 Ledger 程序和 GX10/NAS 均未由此证明。

准确提交的 [Actions 运行 35750476529](https://github.com/kongbu0621/infra-local-hand/actions/runs/35750476529)
分别记录两个平台。Windows 后续检查包括脚本解析、PowerShell 5.1 拒绝、PowerShell 7 准入、精确 ACL、
LocalService Git trust、私钥 ACL、runner 退出码传播和 Junction 拒绝。源码及安装态覆盖按平台记录，不能把跳过合并计为 PASS。
完整 API 记录 Windows job 用时 341 秒、Linux 594 秒；Linux 距当前 600 秒预算仅 6 秒。
本次实际成功，但 CI 时间余量较小，后续需独立评估预算，不把接近上限写成超时或忽略此事实。

先行全量与获取准确提交存在时序重叠，结果虽通过但仅保留作过程记录；表中的结果来自随后独立干净 worktree 的准确验证。
Plugin 首次构建因输出父目录尚未建立失败，保留原记录；建立目录后重试通过，没有修改产品源码。
首轮旧候选的 workspace outbox 异常继续保持未归因；本轮独立临时目录通过不反证旧异常不存在。

## 仍需完成的工作

1. **受监督启动准备：代码缺口。** 原 `_start` 在 broker 进程内做目录、配额与计划文件 I/O；后台线程超时不能证明这些操作停止。
   当前 `SystemdManager.support()` 固定含 `SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED`，其他主机条件齐备也拒绝生产启用。
   这是安全封堵，不能称为完整实现。后续须准确设计已准入根槽位的分配、持久消费和不复用，或独立受限 provisioner 的权限及执行身份；不得临时开放父根写权。
2. **NAS 硬配额 provider：代码和受信事实缺口。** 仍缺准确协议、查询身份、archive/账号/配额域映射和持续强制边界；不使用配置布尔值或本地 quota 冒充网络硬上限。
3. **E3：真实隔离集成。** 补齐实现后仍需真实受限账户、cgroup、进程树/延迟启动/崩溃恢复及配额故障验证；普通 CI 成功不关闭此项。
4. E4 实际连接、E5 GX10/S2 切换、E6 NAS A2 保持后续独立边界。Ledger 已关闭的 A2 主体范围不因此要求重复批准。

后续优先补启动准备与 NAS provider 的准确实施事实；若新增槽位/执行身份或权限模型构成实质设计变更，
按已有 Gate 更新准确文档并取得对应决定，不默默扩展本次 A。无须先重做旧 v1 mailbox，也不能借 validation 绕过 A2 权限。

## 产物摘要

| 产物 | SHA-256 |
| --- | --- |
| wheel，177,903 bytes | `43540b40b6de2dd8c6d08ac1b3163fed298d49851a2186465cd977ded40717eb` |
| Plugin，17,646 bytes | `be8d57485515b31eb4a4700a5fc016c9dcf6c899c2e85156ad01d25912685d29` |
| 完整安装 payload | `cc5b7a1b5fba9a1a93fe0ea352f664395e224e56460265e799ee7eb341ec18be` |

## 证据留存

完整 evidence ZIP：`infra-local-hand-A2-recheck-c8176b0-evidence-20260922.zip`，911,929 bytes、1,069 个成员。
SHA-256：`2f0f02f6c27e1b6fd20d30546c81565f4b9e40c2c402a968257f760019d01ffb`。
独立封存记录：同名 `.zip.seal.json`；绑定外层 ZIP、内层 seal 和成员 manifest 摘要，不声称包含自己的哈希。
保留 24 条外层命令记录、292 条本地安装态命令记录和 633 份 stdout/stderr 日志；分工反例及 CI 日志另按实际文件留存。
ZIP CRC、唯一完整成员集合、逐成员字节/摘要以及 seal → manifest 绑定均通过。
原始反例、命令日志和运行数据只保留在私有交付中，不提交 Public；摘要封存不是数字签名或实机验收证明。
本地 ZIP 保留本轮 292 条安装态逐命令记录及 CI 完整 job 日志、步骤和产物元数据。
Actions 的独立 artifact 二进制仍位于上述运行中；未下载到本地 ZIP，不把索引元数据说成已包含该二进制。
