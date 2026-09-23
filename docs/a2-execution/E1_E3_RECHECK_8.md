# 第八轮实现复核：配置绑定、目录写入、证据与异常恢复

本轮已修复确认的既有缺陷，完成准确候选的源码、构建安装及 CI 验证。**仍不构成可部署候选：E1 受监督启动准备和 NAS 配额适配未完成，E3 真实 cgroup 验收仍阻塞。**

## 准确身份与范围

- 输入 main：`9198c8926c89a1911bcc531b44b7104278663080`。
- 修复源码：`b4146d750873f8a49b4bf0f4ee6702301b3f66c1`；Git tree：`001d2f4e1aa41222bc36df94533a79246964c5af`。
- 源码/测试变更 23 个路径，新增 35 个公开回归方法。测试方法含子场景；专项和私有探针与全量覆盖重叠，不相加。
- 范围为既有 S1 维护及 E1–E3 隔离实现验证；未操作现役 GX10、NAS、私有客户端或服务切换。
- R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、A `79f73faedcd9cde4164b0d1625782dae27db6c2f`、B 事件 `LH-A2-EXEC-MCP-E1-E3-CLOSURE-20260922-01`、C `367632126c1930983a06b1854f63789448633148` 保持原链。直接读取固定 R，三份权威文档与 A 字节一致，C 仅两份治理文件，D 以 C 为祖先。决定核验为仓库保留副本连续性，不冒充独立平台消息认证。
- 未改变依赖、作业目录、七工具契约、Task v1 八动作、许可证决定或阶段授权。生产不支持保护未移除。

## 确认的问题与修复

| 边界 | 原始反例与修复后行为 |
| --- | --- |
| 配置来源 | AuthConfig/Policy 在祖先检查后发生符号链接或普通目录替换时可能接受另一份主体/peer 映射；现绑定祖先身份并在读取前后复核。Policy 拒绝短读的合法 JSON 前缀，清理失败不覆盖原准入拒绝 |
| 目录写入与发布 | Evidence seal、Plugin journal、Plugin build 在目录替换竞争中可能向无关目录创建或移动内容；创建使用已打开目录描述符，写入与发布核验父目录绑定，失败保留现场 |
| 描述符所有权 | AuthorityLock 关闭报错后保留旧 FD 编号，再次关闭可能误关复用编号的其他文件；现先清除自身所有权再关闭一次。证据 ZIP、旧 S1 CAS/安装记录的 fdopen 构造失败现在回收真实 FD 并保留主异常 |
| 服务清理 | 单个 listener/connection close 失败可能跳过后续回收，杀死 accept 循环、泄漏容量或覆盖 startup/构造主异常；现尝试全部已取得资源的清理，健康路径仍报告关闭错误 |
| 临时目录探针 | Ledger 函数及独立解释器探针可能把短写当成功，close 失败跳过 unlink 或覆盖 fsync 异常；现核对准确写入长度，独立尝试清理并保留主错误 |
| 客户端证据 | ZIP 原始名 NUL 被解析库截断、外 seal 重复/错角色、JSON true/1/1.0 等类型混淆可能被接受；现核验原始名称、准确两角色及整数/类型绑定。非法 JSON 常量、递归解析和 callback 序列化错误按结构化错误拒绝 |

这些修复使用合成身份、临时文件系统及受控错误/竞争注入。祖先复核不宣称抵抗任意并发管理员修改的原子保证；错误注入不等于真实故障磁盘或实机验收。

## 准确候选验证

| 环境 | 源码 PASS | SKIP | 说明 |
| --- | ---: | ---: | --- |
| 本地 Linux | 672 | 3 | 单次完整源码；pytest 672 passed, 3 skipped in 343.24s (0:05:43)；前后 HEAD/tree 与干净状态一致 |
| Linux CI | 674 | 1 | 源码 353.19 秒；job 636.0/900 秒 |
| Windows CI（S1） | 202 | 132 | 源码 330.54 秒；job 387.0/900 秒 |

本地跳过原因：

- 1 项：UNSUPPORTED: host policy prohibits AF_UNIX sockets; synthetic transport tests are separate
- 1 项：UNSUPPORTED: this host forbids the real Unix maintenance socket
- 1 项：UNSUPPORTED real systemd/cgroup integration: SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED; PID 1 is not systemd; no predelegated manager admission; dedicated non-root account is required

CI 为 [run 35810885472](https://github.com/kongbu0621/infra-local-hand/actions/runs/35810885472)，push / main / attempt 1，三个 job 均 success。完整 decoded logs、步骤和 artifact metadata 已留存；**未下载 CI artifact ZIP 二进制**。Windows workflow 明确排除 A2 jobs/MCP/Plugin，不能据此宣称 Windows A2 通过。CI 各跳过位置/原因保留在证据 `ci-review.md`，不从数量推定逐项覆盖。

- 本地 wheel 安装态：94 检查、292 命令、584 份 stdout/stderr 通过；命令含预期非零的拒绝用例，不能理解为全部退出码 0。
- 安装态 MCP：外部复制测试在 `-I` 下运行，35 PASS / 0 SKIP。
- 新 build worktree、新 base/MCP venv；使用已存在的九项版本准确固定 builder，并在构建前后核对，未宣称新安装构建工具链。28 个缓存 MCP wheel 重新匹配本候选锁文件后离线安装。
- Python `-W error` 编译、Linux shell 语法、pip check、Plugin 构建与 wheel 安装通过；39 个 payload 文件匹配 Git blobs，13 个 Plugin 成员，完整 payload 摘要 `202e370afd77aaee125dbc2b10e85de6c922080e5356228475beff32e9e51a05`。
- Plugin 仍为 `UNCONFIGURED_E4_REQUIRED`，公开 `mcpServers` 为空；未新增真实连接或授权。

| 产物 | 字节 | SHA-256 |
| --- | ---: | --- |
| `infra_local_hand-0.2.0a1-py3-none-any.whl` | 188762 | `1baf1b6daa9299af52dd41b8c5cb59a5886700dd0a3386115b79a4aef881e648` |
| `local-hand-a2-plugin-0.1.0.zip` | 18625 | `8cd3a89587f758de82039f24c0cef362d9d676a329bc0051fbfdb7e0e2e62aa9` |

## 独立复审和失败保留

六条专项审查与跨模块反向验证分别保留报告：资源锁/CLI、Runner/Ledger/S1、Evidence/Client、Auth/Plugin/Policy。确认的问题均有原始源码反例及修复后验证；原始失败、修复前源码、辅助探针和原始日志保留。最终报告另经独立证据审计，完成后才封存。

结果汇总快照含 121 条已完成命令记录，其中 32 条为非零历史记录；这些包含修复前红例及验证工具错误，不计作最终通过。快照先于自身记录和最终审计，完整 ZIP 的最终记录数另列。

保留的工具问题包括：指定 MCP venv 没有 pytest，随后使用现有 unittest 或已固定 builder；首次 CAS 探针缺 Git fixture；FD 计数误包含取得所有权前的编号复用；JSON 深度/错误类型的初版预期错误；Mock 目标与测试摘要序列化错误；Gate 私有副本多尾换行被摘要检查检出。均保存原稿/输出并纠正，不将工具失败冒充产品缺陷，也不隐藏重试。未因此新增依赖。

R6/R7 既有 ZIP 与外 seal 摘要仍与原交付一致。仓库只公开修复代码与脱敏结论；原始机密治理来源、探针和验证日志保留为私有证据。源码模式扫描仅覆盖本次改变的 blobs，不是全历史秘密扫描保证。

## 仍未完成的出口

E1 受监督启动准备和 NAS 硬配额 provider 仍有代码缺口；`SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED` 保护保留。E3 真实已委派 systemd/cgroup 尚未证明。E4 当前客户端私有连接与实际文件桥接、E5 GX10/S2 切换、E6 GX10→NAS→GX10 A2 均未执行；S2 继续 OPEN。代码/模拟/安装/CI 通过不关闭这些门槛。

## 证据交付

最终独立证据审计通过，审计记录 SHA-256 `6cfbf003fba4346a8657ed7bc3a14f862f48e1cc77b3ff82f7c7cc5709633252`。完整 ZIP 已执行 CRC、成员唯一性、逐成员字节/摘要及内部 manifest 绑定核验，并与外部封存记录一同交付。

| 交付物 | 字节 | SHA-256 |
| --- | ---: | --- |
| `infra-local-hand-A2-recheck8-b4146d7-evidence-20260923.zip` | 11124383 | `acf4e2abc363249924ccfbcf30dec7bb3040ef063b2aa2aebfde02e161f065c9` |
| `infra-local-hand-A2-recheck8-b4146d7-evidence-20260923.zip.seal.json` | 729 | `06422a8bb630659f2f2a9436b2b79f0a5dcf03b2e825fd2ca511e1ffa052b3ac` |

ZIP 含 1507 个成员、126 条结构化命令记录、另有 292 条安装态命令记录和 838 份 stdout/stderr 日志；完整三份 CI decoded logs 另行保留。原始失败、审计、wheel、未配置 Plugin 与已校验依赖 wheel 均在包内。虚拟环境、bytecode 和可重建的 S1 合成仓库内容不作为完整现场交付。

最终结构化命令记录含 33 条非零退出：RESULTS 快照中的 32 条之外，新增 1 条审计工具失败。首审错误要求所有命令的可执行文件都使用绝对路径，实际合法记录为 `git -C ... worktree add --detach ...`；保留首审脚本和失败日志，更正为核验该条准确命令及源码后审计通过。此后未重跑产品测试，也未改写 RESULTS 快照或预封存报告。

封存后生成本节时，辅助脚本的中文 bytes 字面量被 Python 编译拒绝；改为显式 UTF-8 编码后再执行。该工具错误发生在脚本执行前，未改动源码或封存证据；首稿和纠正说明另留发布记录，不计入上述已封存命令数量。

外 seal 的 `archive_name` 与 ZIP 准确配对；摘要记录是完整性封存，不是数字签名或实机验收证明。ZIP 内保存审计对应的预封存报告，本文只在本节补充封存后产生的实际摘要，避免自引用。原始证据未推送 Public；本报告和两个入口文档的后续提交不改变上述已验源码/产物。
