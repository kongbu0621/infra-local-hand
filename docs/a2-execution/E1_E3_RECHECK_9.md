# 第九轮实现复核：完整字节校验、并发资源绑定与恢复边界

本轮修复确认的既有缺陷，并完成准确候选的源码、构建安装及 CI 验证。**部署状态仍为 `E1_INCOMPLETE_E3_BLOCKED_NOT_DEPLOYABLE`：E1 受监督启动准备和 NAS 硬配额适配未完成，E3 真实 cgroup 验收仍阻塞。**

## 准确身份与范围

- 输入 main：`25eeaf839907a71928fc78ad6df1f96254d2e2dd`。
- 修复源码：`330dbfd8f6e12c90fa29dc13e913fdd1ea9fa93d`；Git tree：`7c57f8f99bb657c4dd60345119b7082ade102f83`。
- 源码/测试变更 19 个路径，新增 31 个公开回归方法。方法包含子场景；专项、交叉探针与全量覆盖重叠，不相加。
- 范围为既有 S1 维护及 E1–E3 隔离实现验证；未操作现役 GX10、真实 NAS、私有客户端或服务切换。
- R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、A `79f73faedcd9cde4164b0d1625782dae27db6c2f`、B 事件 `LH-A2-EXEC-MCP-E1-E3-CLOSURE-20260922-01`、C `367632126c1930983a06b1854f63789448633148` 保持原链。直接读取固定 R，三份权威文档与 A 字节一致，C 仅治理登记，D 以 C 为祖先。Owner 决定核验为保留副本连续性，不冒充独立平台消息认证。
- 未改变依赖、固定作业目录、七工具契约、Task v1 八动作、许可证决定或阶段授权；生产不支持保护保留。

## 确认的问题与修复

| 边界 | 原始反例与修复后行为 |
| --- | --- |
| Authority 与账本 | Authority 注册文件短读可隐藏合法 JSON 后的损坏内容；现在读取长度绑定 fstat。账本在检查后消失时，SQLite 不再隐式重建空库，使用正确转义的只打开既有文件 URI；构造中断会回收连接并保留原异常 |
| 配置与客户端身份 | AuthConfig 和 Plugin journal 拒绝不完整读取；Plugin 将畸形 callback/错误对象转成既有结构化错误。部署绑定按规范 JSON 字节区分 true、1、1.0，预检只接受准确引用列表，不把字符串或字典当授权目录 |
| 维护 socket 启动 | 原名上的并发替代物可能被 chmod 或误认为刚绑定的 socket；现在在独占私有 staging 中绑定并固定 inode，经 Linux O_PATH 设置权限，再 create-only 发布并复核父目录/目标身份；缺少能力时不降级为原名 chmod |
| 维护 socket 清理 | lstat 后直接 unlink 可能误删并发替代物；现在先原子捕获到私有隔离目录，再核对是否为原 socket。非原对象采用 create-only 恢复；恢复冲突保留两个对象和私有恢复记录，返回 IO_UNCERTAIN。清理错误不覆盖原始拒绝或启动错误 |
| 临时写入探针 | 命名探针在目录替换及 stat→unlink 窗口可能删除并发文件；Local Hand 自身探针改用绑定目录描述符的匿名 O_TMPFILE inode，核对零链接、准确写入、fsync 与目录身份。函数与独立解释器实现一致；匿名能力不支持即拒绝，不采用命名回退 |
| 服务端证据封存 | 普通目录替换可在最终拒绝前把私有 metadata/产物写入无关目录；现在持有原子发布所需的子目录描述符，并在登记前复核绑定。ZIP 成员上限同时计算生成记录和内部 manifest，避免预算少计 |
| 客户端 ZIP 与安装 wheel | ZIP 声明长度可掩盖压缩终止标志截断、额外压缩/解压内容；现在验证 STORED 长度及有界 DEFLATE 的完整结束、准确展开和无尾随输入，损坏流按 CONFLICT 拒绝。其他未具备同等有界验证的压缩方法在解压前拒绝。保留 wheel 的原始成员名含 NUL 时不得别名到获准 payload/metadata |

这些反例使用合成身份、临时文件系统、归档及受控竞争/错误注入。初次命名临时探针修复残留的 stat→unlink 窗口由交叉复审再次发现，随后才改为匿名 inode；中间修复和失败证据保留。它们不等于真实故障磁盘、GX10 或 NAS 验收。

## 准确候选验证

| 环境 | 源码 PASS | SKIP | 说明 |
| --- | ---: | ---: | --- |
| 本地 Linux | 703 | 3 | 单次完整源码；703 passed, 3 skipped in 344.78s (0:05:44)；前后 HEAD/tree 与干净状态一致 |
| Linux CI | 705 | 1 | 源码 348.12 秒；job 625.0/900 秒 |
| Windows CI（S1） | 203 | 132 | 源码 361.82 秒；job 432.0/900 秒 |

本地跳过原因：

- 1 项：UNSUPPORTED: host policy prohibits AF_UNIX sockets; synthetic transport tests are separate
- 1 项：UNSUPPORTED: this host forbids the real Unix maintenance socket
- 1 项：UNSUPPORTED real systemd/cgroup integration: SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED; PID 1 is not systemd; no predelegated manager admission; dedicated non-root account is required

CI 为 [run 35815185797](https://github.com/kongbu0621/infra-local-hand/actions/runs/35815185797)，push / main / attempt 1，3 个 job 均 success。完整 decoded logs、步骤与 artifact metadata 留存；**未下载 CI artifact ZIP 二进制**。Windows workflow 排除 A2 jobs/MCP/Plugin，不能据此宣称 Windows A2 通过。CI 跳过位置/原因按原始摘要保留，不把 skip group 当成每个测试节点都已逐项列明。

Linux CI 的 2 项真实 Unix socket 测试结论为 **依据完整套件证据推定通过**：固定源码中可定位这些测试，按准确工作流纳入常规 Linux 全量收集范围；套件成功且完整跳过清单不含这些节点。`pytest -q` 未逐一输出已通过节点 ID，因此这不是独立的逐节点 PASS 日志；也不证明 GX10 实机部署。

| 已核对的测试节点 | 结论口径 |
| --- | --- |
| `tests/test_local_hand_jobs_cli.py::CliTests::test_real_unix_socket_roundtrip_when_host_permits` | `PASS_INFERRED_FROM_COMPLETE_LINUX_SUITE` |
| `tests/test_local_hand_jobs_integration.py::JobIntegrationTests::test_real_maintenance_transport_shares_broker_and_original_identity` | `PASS_INFERRED_FROM_COMPLETE_LINUX_SUITE` |

- 本地 wheel 安装态：94 项检查、292 条命令、584 份 stdout/stderr 通过；命令包含预期非零的拒绝用例，不表示全部退出码均为 0。
- 安装态 MCP：外部复制测试在 `-I` 下运行，36 PASS / 0 SKIP。
- CI 安装态：Linux 94 项检查 / 292 条命令；Windows S1 10 项检查 / 10 条命令。
- 新 build worktree、新 base/MCP venv；使用已存在且准确固定的 9 项构建工具版本，构建前后核对。未新安装构建工具链；缓存 MCP wheel 匹配冻结锁文件后离线安装。
- Python `-W error` 编译、Linux shell 语法、pip check、Plugin 构建与 wheel 安装通过；39 个 payload 文件匹配 Git blobs，13 个 Plugin 成员。完整 payload 摘要 `0781b7f0c24d19e1c21eaa7f0be3dde5faeb83050b3a08752231478c4ce083ff`。
- Plugin 仍为 `UNCONFIGURED_E4_REQUIRED`，公开 `mcpServers` 为空；没有据此建立真实连接或扩大授权。

| 产物 | 字节 | SHA-256 |
| --- | ---: | --- |
| `infra_local_hand-0.2.0a1-py3-none-any.whl` | 192680 | `91ec93852b06e9f9c82fce9cf5671ff4dd808955de3a10d95882a657c798d778` |
| `local-hand-a2-plugin-0.1.0.zip` | 18996 | `88a3e8339148aa6c1796fe08d60232ebf38cc4be754b6856d68f79a915274f91` |

## 复审关系与失败保留

各专项及跨模块审查保留原始源码、红例、修复后验证、命令与日志。源码总审结论为 `PASS_WITH_LIMITS`。**作者关系如实披露：源码总审者同时是本轮证据客户端补丁作者；该客户端补丁由另一名 evidence 审查者独立读审和运行反例。**其对其他分工的复审属于独立交叉检查，不能概括成所有路径均由完全无作者关系的审计者验收。最终完整证据报告还需在本预封存报告生成后接受独立审计，审计通过后才封存。

RESULTS 汇总快照含 128 条已完成命令记录，其中 23 条为非零历史记录。快照先于自身记录和后续审计/报告，完整 ZIP 最终计数另列。非零记录包括产品红例、中间修复遗漏及验证工具问题，不计作最终通过；不同分工和全量测试计数不相加。

保留的工具问题包括：错误调用 Python 源文件的启动参数；探针误命中标准库临时目录检查；断言错误要求 metadata 仍留在 staging 而忽略原有已绑定目的目录；FD 计数包含后来新增的父目录/隔离目录描述符；Plugin 测试误用接口或返回结构；Path.lstat 钩子在改用 os.stat 后不再触发；过严要求合法 UNSUPPORTED 必须改为 IO_UNCERTAIN。相应原稿与输出均保留、纠正，并与真实产品缺陷区分，不以工具失败扩大缺陷数量。

CI 采集另保留 3 项工具问题：首次按假定 workflow 路径读取发生 fetch error，随后按 run 的真实 workflow 路径更正；workflow 副本因复制工具增加尾换行而与原摘要不符，随后按原始响应恢复准确字节。Windows 大日志的原始响应首次落盘失败，随后从执行器内存保存的完整响应恢复；原响应身份与日志内容完整，无法恢复的原请求起止时间保持 null，steps 重新只读获取并保留。原副本、响应与纠正记录保留；这些是采集问题和明确的采集时间缺口，不是源码、构建或 CI 产品测试失败。

既有 R6/R7/R8 封存证据按只读边界保留，本轮使用独立证据目录。Public 只提交代码与脱敏结论；原始治理来源、探针、日志、主机目录与恢复记录不进入 Public。本次改变内容的模式扫描不构成全历史秘密扫描保证。

## 保留的实现边界与尚未完成的出口

- **标准库命名探针仍存在。** 实际解释器仍调用真实 `tempfile.gettempdir()` 观察选址与回落；Python 标准库内部可能创建并 unlink 命名测试文件。本轮仅消除了 Local Hand 自身写入探针的命名清理，没有证明任意同 UID 并发干扰下标准库内部操作安全。没有预填 `tempfile.tempdir` 缓存或替换选择算法，以免弱化真实回落观察。
- **socket 失败可能需要可信恢复。** 随机私有 staging/隔离目录依赖独占 ownership，不承诺抵抗拥有相同服务账户权限或更高权限者任意改写。捕获到并发替代物后若原名又被占用，既不覆盖新对象，也不删除被捕获对象；保留隔离 entry、可用的私有恢复记录并报告 IO_UNCERTAIN。目录身份不明或恢复记录写入失败同样保留可能残留，不能把关闭返回失败解释成目录已清空；后续应由受信执行者核对恢复。
- Linux O_TMPFILE、O_PATH 和内核 FD 视图缺失时对应检查拒绝，不能回退到不具备同样边界的命名删除或 chmod。受控 inode 探针与云端 Linux CI 不能替代实际运行账户、文件系统权限、GX10 身份和资源委派验证。
- E1 受监督启动准备与 NAS 硬配额 provider 仍未实现，`SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED` 等生产保护未移除。E3 真实已委派 systemd/cgroup 尚未证明。E4 当前客户端私有连接与实际文件桥接、E5 GX10/S2 切换、E6 GX10→NAS→GX10 A2 均未执行；S2 继续 OPEN。

上述限制对应状态 `E1_INCOMPLETE_E3_BLOCKED_NOT_DEPLOYABLE`；源码、隔离测试、安装态和 CI 通过均不关闭后续门槛。

## 证据交付

最终独立证据审计通过，审计记录 SHA-256 `471bad4550b2eab010c93b7a4e2beb8a5aede5c899bf7b3f7bee0e91ef839a20`。完整 ZIP 已执行 CRC、成员唯一性、逐成员字节/摘要及内部 manifest 绑定核验，并与外部封存记录一同交付。

| 交付物 | 字节 | SHA-256 |
| --- | ---: | --- |
| `infra-local-hand-A2-recheck9-330dbfd-evidence-20260923.zip` | 11249286 | `0d418038c37fd3875d642cd9ad010f5c9e8b850b6a30c4cd417dac2aa38f194b` |
| `infra-local-hand-A2-recheck9-330dbfd-evidence-20260923.zip.seal.json` | 729 | `4113a949980d10bc78b7353c7756f74b2336d1fb1fcebf44bc01db0146e500cb` |

ZIP 含 1564 个成员、135 条结构化命令记录、另有 292 条安装态命令记录和 856 份 stdout/stderr 日志；完整三份 CI decoded logs 也在包内留存。原始失败、审计、wheel、未配置 Plugin 与已校验依赖 wheel 均在包内。虚拟环境、bytecode 和可重建的 S1 合成仓库内容不作为完整现场交付。

最终结构化命令记录含 23 条非零历史退出；包含修复前反例、中间修复遗漏及验证工具错误，按各分工与审计报告区分保留，不计为最终通过。

外 seal 的 `archive_name` 与 ZIP 准确配对；摘要记录是完整性封存，不是数字签名或实机验收证明。ZIP 内保存审计对应的预封存报告，本文只在本节补充封存后产生的实际摘要，避免自引用。原始证据未推送 Public；本报告和两个入口文档的后续提交不改变上述已验源码/产物。
