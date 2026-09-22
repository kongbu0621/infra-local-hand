# E1–E3 第二轮实现复核

日期：2026-09-22（UTC）。

审查输入为 `e8231bce4165ca933e33a06a22f904c906d0a152`；产品修复提交为 `f109a4df4237a42fe2c6edb9c2435e4b0104fcdd`。补齐 CI 发现的测试夹具生命周期修复后，最终源码为 **`b0b37cd8714497fd6d6edc3c1115c274af8ad17e`**，tree 为 `55371d26acb0f41236064954182f137e03cf995e`。两者仅有两个测试文件的差异，产品 Git blobs 未变；最终产物仍按新提交独立重建验收。本记录补充[前轮复查](E1_E3_RECHECK.md)，不沿用旧候选的验收计数。结论仍为 **E1 有实现缺口、E3 未完成，不可部署**。

范围保持已批准 `LH-A2-EXEC-MCP-v1` 的 E1–E3。规则 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 本轮重新读取固定来源；独立登记 C `367632126c1930983a06b1854f63789448633148` 仍为源码祖先；Owner 继续修复及直接 main 发布授权保持。批准 A `79f73faedcd9cde4164b0d1625782dae27db6c2f` 的需求、架构和实施方案三份原文不变。没有新增 job/tool、扩大运行权限或解除生产阻断。

## 确认问题与修复

| 交界 | 已复现问题 | 本轮修复 |
| --- | --- | --- |
| 构建来源 | setuptools 解析 distribution metadata 后，干净 checkout 切换可令旧 README 元数据与新提交来源标记混入同一成功 wheel；prepared metadata 也缺少跨 hook 来源绑定 | 在 setup 前冻结来源，复制、metadata 持久化及归档结束后复核；PEP 517 prepared metadata 绑定提交与成员摘要；拒绝 skip-build 绕过；失败产物保留但不记为已验证构建 |
| 当前授权 | JWT 在读取 HTTP body 或排队派发期间过期，旧 principal 仍可进入 broker；manifest 读取中撤权后仍可返回目录 | body 读取后、实际 broker 派发前复核当前令牌与准入 client/resource；manifest 返回前再次授权；已经持久受理的作业不因旧请求令牌过期被改写为取消 |
| 控制传输 | 逐次 socket timeout 可被慢速持续收发延长；私有响应预算未生效；CLI 接受歧义或非法 JSON/envelope；关闭后 handler 仍可派发；构造/任务创建失败泄漏资源 | 使用绝对单次请求期限及既有上限与私有预算的较小值；严格有限响应解码；关闭后拒绝新派发，已进入 broker 的调用保留槽位至实际返回；失败路径关闭已打开账本、未启动 coroutine 并归还未使用槽位 |
| 监督与来源清单 | 单次 inspect/stop 异常使唯一监督线程退出；已交付 manager 请求的 guard 回执异常丢失受控句柄；缺失/扫描失败目录误报完整；中间目录替换或扫描后增件绕过清单 | 原句柄保留 UNKNOWN 后继续有界观察/停止，同一已交付身份只恢复观察、不重放 start；缺失、非规范根和扫描错误失败关闭；固定目录 FD，散列后复核目录身份与完整成员集合 |
| 迟到结果与资源租约 | 原业务暂时 UNKNOWN 后已受理 reconcile；迟到业务结果会释放该轮租约，或使 reconcile 与原 evidence helper 并行；取消排队轮次也可误释放仍在封存的父任务资源 | 同事务检查同父非终态轮次及父活动阶段；保留已受理轮次和封存任务的租约；父任务仍活动时 reconcile 保持原 ID 排队，待父 helper 完成 |
| 证据与下载 | descriptor 角色可使 ZIP 绕过 ZIP 校验；轮次与 seal 脱离；ZIP 超预算直到写完才拒绝；客户端成员预算接受非法值 | 绑定角色、artifact ID、seal 及 reconcile ID；每次 ZIP 写入前限额，失败残留不越界且不登记；成员预算要求正有限安全整数，保留原逐件与整体摘要验证 |
| Registry 与 Plugin | prepared bindings 额外键可覆盖服务端计划来源；journal 目录换位可重建 ID；发布清理误删并发替换文件；读回新 inode 或同 inode 新内容可改变已保存身份 | 限定原 source_commit 和五项 payload 摘要；固定 journal 目录与 dirfd；create-only rename 不删除冲突残留；自身成功发布必须读回相同对象及内容，并与已存在的同 intent 赢家路径分别处理 |

CI 仅将 semantic-core job 的超时从 10 分钟调至 15 分钟；本轮保留全部步骤、断言、矩阵及运行时作业预算。这是 CI 调度余量调整，不是验收门槛降低。

## 定向反例与已完成验证

先保存原失败，再执行对应修复。来源包括真实 setuptools wheel/PEP 517 hook、真实 SQLite 事务与文件系统，以及明确标记的签名令牌 ASGI、监督器和宿主回调合成夹具。以下是不同范围的最后一次定向结果，**不相加充当全量覆盖**：

| 定向范围 | 实际结果 | 对应私有原日志 |
| --- | --- | --- |
| 构建身份、deployment、configuration | 37 PASS，0 SKIP；其中 11 个新增构建案例使用真实 wheel/hook | `build-identity-targeted-final.txt` |
| CLI、MCP auth/server | 43 PASS，1 SKIP；跳过为宿主禁止 AF_UNIX 的真实 socket roundtrip | `auth-transport-final.stdout.log` |
| Runner、固定 Ledger | 33 PASS，1 SKIP；跳过为真实委派 systemd/cgroup 集成 | `runner-ledger-targeted-final.log` |
| Evidence server | 27 PASS，0 SKIP | `evidence-post-server.txt` |
| Evidence client | 17 PASS，0 SKIP；包含实际 16 MiB 非高压缩 ZIP 的中断续传、完整 SHA-256 与成员回读 | `evidence-post-client-final.txt` |
| Broker、resources | 42 PASS，0 SKIP；新增迟到结果 3 项原先均 FAIL，修后均 PASS | `broker-resources-targeted.log`、`broker-late-exit-red.log`、`broker-late-exit-green.log` |
| Registry、Plugin | 52 PASS，0 SKIP；与先前含 integration 的 54 PASS/1 SKIP 命令范围不同 | `registry-plugin-final-frozen/stdout.log` |

六路审计及额外 Plugin 独立复核均已记录。Plugin 独立复核另外确认同 inode 原地替换遗漏，修复后原反例单独重跑 1 PASS；该项已在上述最终 Registry/Plugin 集合中，不重复计数。各路针对改动文件的编译与 diff 检查通过；准确候选的完整验证以下表结果为准。

保留早期失败记录，包括 runner inventory 首次组合中夹具临时目录缓存未恢复所致的额外测试错误；修正夹具后，两项真实产品失败已在生产修复前分别再次确认。不能把早期失败删去或混为最终 PASS。

## CI 发现的夹具问题与保留失败

先行 `f109a4d` 的本地准确源码为 547 PASS / 3 SKIP，安装态为 94 检查 / 292 命令，MCP 为 26 PASS。
随后 [CI 35757160205](https://github.com/kongbu0621/infra-local-hand/actions/runs/35757160205) 的 Windows
完整成功（190 PASS / 120 SKIP，安装态 10/10，8 个专项步骤成功）；Linux 为 **548 PASS / 1 FAIL / 1 SKIP**。
失败发生于 `StateLookupChainTests.test_conflict_lookup_error_never_executes_blocked_task` 的临时裸 Git
仓库清理阶段，返回 ENOTEMPTY；Linux 后续 Plugin、wheel、安装与 smoke 步骤均未执行，不能沿用本地通过代替。

真实 Trace2 调查确认 fixture 生命周期存在后台写入入口：每次原场景启动 8 个自动维护子进程，
其中 3 个来自未受控的 fixture 命令、5 个来自裸仓 receive-pack；`file://` 接收端未继承客户端的命令级配置。
三个本地原场景均未重现 ENOTEMPTY，因此 **CI 当次的具体写入者没有直接采样，维护竞态归因仍是与机制一致的推断**。
本轮已确证并修复该夹具生命周期缺陷：fixture 命令和独立裸仓接收端均关闭自动维护；原清理断言保留。
新增真实链路 Trace2 用例修复前 FAIL、修后 PASS；相关三模块 40 PASS / 0 SKIP。
修后一次原场景记录 5 个 receive-pack、0 个维护子进程、0 次 detach。没有以 sleep、重试清理或忽略错误改写验收。
新候选重新运行完整本地和平台验证；原 CI 失败、前后 Trace2 与两个候选的完整记录分别留存。

## 准确冻结候选的完整验证

| 项目 | 实际结果与边界 |
| --- | --- |
| 云端 Linux 源码 | `548 passed, 3 skipped`；Python 3.12.14，`-W error`；准确提交的干净工作树前后复核，pytest 报告 335.02 秒 |
| 编译、shell、构建 | 全部编译、Linux bootstrap 语法、wheel 与独立 Plugin 构建通过；Plugin 13 成员逐件摘要与来源核对，保持 `UNCONFIGURED_E4_REQUIRED` |
| 基础安装态 S1 | 全新基础环境，`94` 项检查、`292` 条命令通过；隔离本地临时验收目录；完整逐命令记录留存 |
| MCP 安装态 | 基础和 MCP 各一个全新独立 venv；MCP 环境按冻结哈希锁安装、两环境 pip check 通过；MCP 环境脱离源码路径的 auth/server `26` 项通过、0 跳过，含真实 loopback HTTP/SDK |
| 安装与产物身份 | 基础和 MCP 安装的完整 39 文件 payload 摘要一致；实际 broker/MCP 入口及来源核验通过；基础安装缺少 extra 时明确拒绝 |
| 批准链与差异 | A 三文档逐字节未变，C 祖先、diff 与准确来源检查通过；新增文本的私人路径/凭据模式检查未命中，仅为有限模式扫描 |
| Linux CI | 完整 job 成功；源码 `550 passed, 1 skipped`，安装态 `94` 项检查、`292` 条命令通过；Plugin、wheel、Linux repeat-bootstrap smoke 均通过 |
| Windows CI | 完整 job 成功；源码 `190 passed, 121 skipped`，安装态 `10` 项检查、`10` 条命令通过，8 个 Windows 专项步骤全部成功；不证明新 jobs/MCP/Plugin 的 Windows 支持 |

本机两项真实 Unix socket 因宿主 EPERM 跳过；另一项真实 systemd/cgroup 集成同时列出代码缺口
`SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED` 及环境缺少 PID 1 systemd、预委派 manager、独立非 root 账户。
不能把三项跳过说成通过，也不能全归因于宿主环境。真实七接口组合仍使用合成 manager/业务结果；
上述测试不证明真实 Ledger 已经在生产监督器下执行。

最终准确候选的 [Actions 运行 35758947374](https://github.com/kongbu0621/infra-local-hand/actions/runs/35758947374) 整体成功。
Linux job 为 624/900 秒，余 276 秒；Windows 为 370/900 秒，均未超时。
CI 的 `pytest -q` 日志未逐项列出跳过原因，因此不靠汇总数量推断 Linux 唯一跳过项，也不据此解除生产阻塞。
Windows 从前候选的 120 SKIP 变为 121；本次新增 Trace2 回归在源码中明确限定 POSIX，
未移除旧平台断言。该范围说明不冒充逐项 skip 日志。

## 产物摘要

| 产物 | SHA-256 |
| --- | --- |
| wheel，181,156 bytes | `ee4fa507a3ff46c2db1e32f7eefb5976fa49c9f1ee27fac3ecb4a1f11e4d49f5` |
| Plugin，18,048 bytes | `9cc3f4b8d62307bc287d862c8c01149f29a92bb57e1eac0acae72fffebe2f063` |
| 完整安装 payload | `b6148bc8234e99a95e34fe47cbc145f389fe605517a5f93996256068043ff42e` |

## 当前仍未完成的事项

- **E1 受监督 bootstrap 尚未实现。** 正式 helper 启动前的目录、plan 与 quota I/O 尚不满足独立监督边界；`SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED` 保持无条件生产拒绝。这是已确认实现缺口的阻断，不是完成 bootstrap。
- **E1 NAS hard-quota provider 尚缺。** 本轮未新增生产 provider，不能把路径检查或合成测试视为真实 NAS 配额保证。
- **E3 真实隔离 systemd/cgroup 验收未完成。** 此项明确 SKIP/UNSUPPORTED；其余源码或传输测试通过不能替代真实进程树、启动撤销与预算证明。因此仍不能将候选称为可部署或 E1–E3 整体完成。
- **E4–E6 不在本轮授权范围。** 当前 Work 的实际认证回调→宿主 writer 桥、GX10/S2 服务切换和真实 NAS A2 尚未验收；16 MiB 下载采用合成已认证回调，不是 E4 实接证明。S2 保持 OPEN。
- **历史 S1 workspace outbox 异常仍未归因。** 本轮即使在 `/tmp` 隔离目录完成准确候选验证，也不能倒推该异常已解释、已修复或关闭。

原失败、命令记录、日志和独立审计保持私有。公开记录仅保留经过核实的修复摘要、准确候选与验证状态，不包含私人目录、账户、令牌或原机器证据。

## 证据与发布

本轮 evidence ZIP：`infra-local-hand-A2-recheck2-b0b37cd-evidence-20260922.zip`，1,854,221 bytes、2,104 个成员。
SHA-256：`c3f36fd667c19257b26103ecc45d8d8ee85fc0ff09bfe91e7420198f961ccefb`。
独立封存记录：同名 `.zip.seal.json`，绑定外层 ZIP、内层 seal 和逐成员 manifest，不自引用自己的哈希。
保留 54 条外层命令记录、两个候选共 584 条安装态逐命令记录及 1,276 份 stdout/stderr 日志；分工审计及 CI 原始日志另按实际文件保留。
这些记录包括失败反例和不同候选的重复验证，不作为去重后的通过数量。
ZIP CRC、唯一完整成员集合、逐成员字节/摘要及 seal→manifest 绑定均通过，独立 `unzip -t` 也通过。
本地两个候选的安装态逐命令记录完整收录。Actions artifact 二进制仍位于各自运行，未下载到本包；
包内保留其 API 索引元数据及完整 job 日志，不把索引当成已收录二进制。

原始审计、失败反例、命令记录和日志保持私有；公开只发布修复源码、测试及本摘要。
证据摘要封存不是数字签名或 GX10 实机验收证明；批准文档 A、旧证据与现役部署均未替换。
源码提交与本报告分开，报告提交不充当 wheel 的源码身份。
