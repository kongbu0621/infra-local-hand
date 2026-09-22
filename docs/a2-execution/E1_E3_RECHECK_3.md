# E1–E3 第三轮实现复核

日期：2026-09-22（UTC）。

审查输入为 `a9f3ade644667054888a4450928d665df3f585f1`。本轮修复及准确验证源码为 **`69461b40bf2e1ac7826e470bea642e5e3d837863`**，tree 为 `d248e317e2b64aa212c259cf73163814ff4fc84c`。本记录补充[第二轮复核](E1_E3_RECHECK_2.md)，各候选的验证结果分别保留。结论仍为 **E1 有实现缺口、E3 未完成，不可部署**；已完成的源码、构建和安装验证不能替代真实监督与后续接入验收。

范围保持已批准的 `LH-A2-EXEC-MCP-v1` E1–E3。规则 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 本轮重新读取固定来源并核验摘要；批准 A `79f73faedcd9cde4164b0d1625782dae27db6c2f` 的需求、架构、实施方案原文逐字节未变；独立 CLOSED 登记 C `367632126c1930983a06b1854f63789448633148` 仍为本轮源码祖先。Owner 继续修复及直接 main 发布授权保持，R → A → B → C → D 顺序未改变。没有新增作业类型、权限、依赖或真实部署配置，也没有解除生产阻断。

## 已确认的边界问题与修复

| 边界及需求映射 | 输入候选上的已确认问题 | 本轮修复 |
| --- | --- | --- |
| 构建与保留 wheel；AX-R10，AX-V01/V10 | payload 标记后安装副本变化仍可成功归档；prepared metadata 初次检查后变化未被最终 wheel 拒绝；普通构建的生成 METADATA/entry_points 也缺少最终绑定；保留 wheel 加入未登记 import 包仍可通过校验 | 最终 wheel 核对准确 payload 成员及字节；归档前固定生成 distribution metadata，并复核成员与摘要；有 prepared metadata 时另外核对原 hook 绑定；保留 wheel 拒绝 payload 与准确 distribution metadata 范围之外的成员 |
| Plugin 发布；AX-R07/R10，AX-V07/V10 | link/unlink 发布清理可误删并发替换的暂存条目；最终输出换位可使返回摘要与文件脱离；链接祖先可绕过输出不得位于源码树的限制 | 改为 create-only 原子 rename，保留失败残留；持有文件描述符，固定输出目录与命名条目身份，返回前复核内容；拒绝链接输出祖先；独立复核发现的同 inode 改写遗漏另见下节 |
| 当前签名密钥准入；AX-R08，AX-V09 | SDK 已认证对象在 body 读取或 executor 排队期间，签名 key 被移除、同 kid 换 key、刷新失败或缓存过期后仍可进入 broker | 认证对象绑定准确 JWK 与 kid；每次导出 principal 都读取同一不可变 key/期限快照，既有 body 后和实际派发前检查因此拒绝过期准入；broker 线程不执行 issuer 网络请求，同 key 的健康刷新仍允许原有效身份 |
| 全局执行容量；AX-R02/R04/R05，AX-V04/V05/V08 | 启动回执丢失或恢复附着失败时，持久执行意图不在内存 `_active` 中，另一资源的作业可越过 `max_running` | 在启动围栏及事务内，合并活动观察者与尚无准确退出证明的持久当前阶段意图计数；仅在后续启动已封阻且进程树退出得到证明后释放执行槽位；同一执行不重复计数，UNKNOWN 的副作用资源屏障另行保留 |
| 捕获初始化与关闭；AX-R02/R04/R07，AX-V04/V07/V08 | 子进程已启动后，selector 或 stdout/stderr 日志初始化失败会遗留直接子进程和 pipe；一个日志 fsync 失败会跳过后续流的关闭 | 将启动、selector、日志初始化纳入同一清理边界；仅终止并有界等待本次直接子进程，逐个关闭 pipe 和日志；保留原异常，独立持久化失败仍上报；不把直接子进程退出替代整个 cgroup 退出证明 |
| 维护入口初始化；AX-R04/R09，AX-V04/V10 | bind 成功后 chmod/listen 失败关闭了 listener，却留下自己的 socket 条目，阻止后续启动 | 在 chmod/listen 前固定创建条目身份，失败时仅清理仍匹配的 socket；身份不明或并发替换保留；初版修复引入的二次启动问题另见下节 |
| 下载完成与恢复；AX-R07/R09，AX-V07/V08 | final rename 后目录 fsync 失败留下合法文件，后续 writer 可不重试持久化便报完成；下载目录在其私有父目录中的条目未同步 | 新完成和已完成重取均重新核对摘要、fsync final 文件，再同步绑定下载目录及父目录，随后复核身份；失败保留文件并上报，健康重试沿用同一 artifact，不重取 ZIP chunks 或重新提交作业 |

密钥检查证明的是当前缓存的签名准入，不能宣称 issuer 独立撤销立即传播；已持久受理的业务也不会因后来 token/key 到期被改写为取消。文件与构建检查拒绝已观察到的变化，不承诺抵御返回后任意高权限改写；构建和运行目录仍须受保护。

CI 本轮仅增加 `pytest -rs`，使准确运行保留分组跳过原因；原矩阵、断言、步骤及 15 分钟 job 预算保持。

## 独立复核与保留失败

五路有边界的审计覆盖 broker/策略、runner/Ledger、认证/控制传输、证据/下载及构建/Plugin；跨路复核另外检查 broker 阶段容量、runner 清理、auth/CLI 及最终构建发布。真实 setuptools、SQLite、文件系统和子进程案例与合成 supervisor、issuer、宿主回调分别记账。

以下两类修复期问题没有混写为输入候选原有缺陷：

- CLI 初版失败回滚会在同一实例第二次 `start()` 时关闭原正常 listener，并遗留新尝试的 listener。独立复核保留该版本的失败，修复为在分配前拒绝已启动或关闭的实例；最终测试核对原 listener 和 socket 条目仍保留。
- Plugin 初版最终回读为容忍 rename 而漏比 ctime，同 inode 改写、保持大小并恢复 mtime 后可返回错误摘要。独立反例保留；修后在 rename 完成后冻结完整身份，包括 ctime 与 link count，再核对最终 hash 前后持有描述符和命名条目。独立复核另补齐普通构建生成 metadata 的最终绑定。

验证器自身的失败也完整保留：prepared metadata 首次用例受 PEP 517 改写 `sys.argv` 影响，修正夹具后先再次证明产品反例；broker 私有探针首次错误地要求封存失败覆盖已成功的业务结果，修正为既定 SUCCEEDED / DURABILITY_UNKNOWN 分离语义；批准链验证器最初依赖未安装的 PyYAML，改为标准库后又有无依据的“至少十个 Python block”断言，最终按实际七个 workflow block 编译核对。它们属于夹具或验证器问题，不计作产品缺陷，也不删除以伪装全部首次通过。MCP 依赖安装的一个警告同样保留；该命令最终退出 0，冻结哈希约束未放宽。

| 定向范围 | 最后一次定向结果及限定 |
| --- | --- |
| Broker、policy、resources、contract | 79 PASS / 0 SKIP；两个全局容量反例均先 FAIL 后 PASS，另核对恢复取得退出证明后可放行独立资源作业 |
| Runner、固定 Ledger | 35 PASS / 1 SKIP；真实子进程初始化清理，以及日志 fsync 失败时所有流仍关闭的边界通过；跳过为真实委派 cgroup 集成 |
| Auth、MCP server、维护 CLI | 52 PASS / 1 SKIP；跳过为宿主禁止真实 AF_UNIX；注入 listener 的真实 socket 类型 inode 案例不冒充真实传输 |
| Evidence server/client | 46 PASS / 0 SKIP；两个完成持久化反例先 FAIL 后 PASS；含真实 16 MiB 低压缩 ZIP 的续传与成员核验，认证回调为合成 |
| Build identity、deployment、configuration、Plugin | 74 PASS / 0 SKIP；真实 wheel/hook 与 Plugin 文件发布负例；build identity 的 16 项 wheel 案例跨平台保留，4 项 Plugin 发布案例明确仅 Linux |

这些范围存在重叠，不能相加作为全量用例数。早期部分 auth 命令只有合并日志，没有准确起止时间；私有索引如实注明时间缺失，不补造。后续记录含实际命令、时间、退出码及独立 stdout/stderr 摘要。各路定向检查来自当时审查工作树；完整结论以下述准确冻结候选验证为准。

## 准确冻结候选验证

| 项目 | 实际结果 |
| --- | --- |
| 云端 Linux 源码 | **572 PASS / 3 SKIP**；Python 3.12.14、`-W error`、`-rs`；pytest 343.67 秒。独立工作树前后均干净，HEAD/tree 均匹配本报告准确源码 |
| 编译与构建 | 源码、测试及 Plugin 编译，Linux bootstrap shell 语法，wheel 与 Plugin 构建通过；Plugin 13 成员摘要/来源核对，保持 `UNCONFIGURED_E4_REQUIRED` |
| 基础安装态 S1 | 全新独立环境，**94 项检查 / 292 条命令通过**，584 份 stdout/stderr 日志逐件核验；来源身份在安装态恢复测试后再次通过 |
| MCP 安装态 | 另建独立 venv，按冻结依赖哈希安装；脱离源码工具目录的 auth/server **30 PASS / 0 SKIP**，包含真实 loopback HTTP/SDK；两环境 pip check 通过 |
| 完整安装身份 | 基础/MCP 两环境及准确源码的 39 文件 payload 摘要一致，实际 broker/MCP 入口和来源绑定通过；基础环境没有 extra 时明确拒绝 |
| 批准链与公开差异 | A 三原文未变，C 祖先验证通过；七个实际 workflow Python block 编译通过，diff 检查及改动源码的有限凭据模式扫描通过；模式扫描不构成穷尽秘密保证 |
| Linux CI | **574 PASS / 1 SKIP**；源码 342.12 秒；安装态 94 项检查 / 292 条命令通过；Plugin、wheel、bootstrap 语法及 repeat-bootstrap smoke 通过 |
| Windows CI | **195 PASS / 125 SKIP**；源码 295.93 秒；安装态 10 项检查 / 10 条命令通过；8 项 Windows 专项步骤全部通过 |

准确源码的 [Actions 35764764639](https://github.com/kongbu0621/infra-local-hand/actions/runs/35764764639) 为 push/main、attempt 1，整体 SUCCESS；各平台无失败步骤。Linux job 613/900 秒、余 287 秒，Windows 360/900 秒、余 540 秒。`-rs` 明确记录 Linux 唯一跳过为受监督 bootstrap 尚未实现、无预委派 manager 及独立非 root 账户条件未满足；Windows 95 组理由合计 125 项，包括 4 项 Linux 专属 Plugin 发布案例。分组理由不冒充每个被跳过 test node ID；Windows 忽略新 jobs/MCP/Plugin 源码模块，其成功覆盖既有 S1 和跨平台构建，不证明这些新功能已支持 Windows。

本机三项跳过已逐项记录：真实 CLI Unix socket 和七接口集成的 Unix 维护 socket 均被宿主禁止；真实 systemd/cgroup 集成同时存在代码缺口 `SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED`、PID 1 非 systemd、无预委派 manager 及独立非 root 账户条件缺失。第三项不能全部归因于环境，也不能被合成测试替代。上述安装和传输验证不证明真实 Ledger 已在生产监督器下执行。

## 产物摘要

| 产物 | SHA-256 |
| --- | --- |
| wheel，182,686 bytes | `bcb237257cfad989b53c56c0758253f6563929634a609dd495da4c06594b90a8` |
| Plugin，18,046 bytes | `bd8e5bdbbae0bce558f39994a614698ca5a37144e0c68564d645d5728c42cae9` |
| 完整安装 payload，39 文件 | `cd8ed2bb258acdf133abaf64fc754ba646087d6b6869018237e0af44b06975ab` |

## 当前未关闭的门槛

- **E1 受监督 bootstrap 尚未实现。** helper 启动前的目录、plan、quota I/O 仍不满足独立监督边界；`SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED` 保持无条件生产拒绝。此次直接子进程清理与容量修复不关闭该缺口。
- **E1 NAS hard-quota provider 尚缺。** 没有新增生产 provider；路径校验、有限本地预算及合成测试不能证明真实 NAS 配额。
- **E3 真实隔离 cgroup 验收未完成。** 真实进程树、延迟启动撤销、崩溃恢复及预算证明仍缺，因此不能宣称 E1–E3 全部完成或候选可部署。
- **E4–E6 未执行，也不在本轮授权内。** 当前 Work 实际认证回调到宿主 writer 的交付桥、GX10/S2 切换、真实 NAS A2 仍未验收；S2 保持 OPEN，旧环境和历史证据不变。
- **历史异常继续保留。** S1 workspace outbox 异常仍未归因；本轮隔离临时目录通过不能倒推该问题已关闭。第二轮 CI 清理失败的具体写入者未被直接采样，其机制调查与归因限制仍按旧报告保留。

## 私有证据与发布

本轮完整 evidence ZIP 与独立封存记录均已保存为私有交付文件：

| 项目 | 准确记录 |
| --- | --- |
| ZIP | `infra-local-hand-A2-recheck3-69461b4-evidence-20260922.zip` |
| 大小与成员 | 930,032 bytes；1,142 个唯一成员 |
| ZIP SHA-256 | `edb6a0237ede0ea90301f9756d256cb7b8aeb593dd5af3eccee1fff8bef58a08` |
| 外部 seal | `infra-local-hand-A2-recheck3-69461b4-evidence-20260922.zip.seal.json` |
| seal SHA-256 | `8312f1d627cd0dcc66bb4a317489124ccd3442f08ed36e3e73014e8149268e5c` |
| 命令与日志 | 59 条外层结构化命令记录，另有 292 条安装态 S1 命令记录；702 份独立 stdout/stderr 日志；早期合并日志与 CI 作业日志另外保留 |
| 封存核验 | ZIP CRC、唯一且准确的成员集合、逐件大小与 SHA-256、manifest 与内外 seal 绑定及独立 `unzip -t` 均通过 |

包内保留原失败、修复期探针、准确候选源码/构建/安装验证记录、wheel、未配置 Plugin 及 CI 原始响应和完整作业日志；虚拟环境、缓存和可重建的 S1 合成仓库载荷不入包，符号链接仅作为数据记录。早期缺失命令时间的限制见上文。封存后的发布与交付回执另存，不反写已经固定的证据包。

原失败、命令、日志、合成夹具输入和原始审计保留在私有交付物，公共仓库仅发布修复源码、测试及核实后的摘要。本包保留两项 Actions artifact 的 API 索引和完整三项作业日志；其 artifact ZIP 二进制未下载入包。封存摘要不是数字签名或 GX10 实机证明。源码提交与本报告提交分开；报告提交不充当 wheel/Plugin 的源码身份，批准文档 A 与旧证据均不替换。
