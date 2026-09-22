# E1–E3 首轮实现与验证记录

日期：2026-09-22。结论：**实现检查点，E1–E3 整体尚未完成，不可部署。**

后续从本记录的发布提交继续复查，另发现启动准备监督缺口并修复多处边界问题；准确修复候选及新结果见[实现复查记录](E1_E3_RECHECK.md)。本页保留首轮结果。
本记录不修改批准基线、接口或后续阶段权限；真实 GX10、S2、OAuth 接入及 NAS A2 未执行。

## 准确来源与顺序

| 项目 | 固定身份 |
| --- | --- |
| 规则 R | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` |
| 批准文档 A | `79f73faedcd9cde4164b0d1625782dae27db6c2f` |
| Owner 决定 B | [E1–E3 开工决定](../governance/A2_EXEC_E1_E3_OWNER_DECISION.md)，事件 `LH-A2-EXEC-MCP-E1-E3-CLOSURE-20260922-01` |
| 独立开工记录 C | `367632126c1930983a06b1854f63789448633148` |
| 实现 D | `54d0a9909c1d5ca6c732ac190e67d4952d580556` |
| D tree | `78b45091ddc648979d705befe2e4c6436e1789be` |

D 的直接父提交为 C。三份权威文档与 A 逐字节相同；本记录另为文档提交，
不把验证记录提交误写为所测 wheel 的来源。C 不含实现，未压缩合并开工与实现历史。

## 实现和已修复的交界

`0.2.0a1` 包含独立 job 契约、持久 broker、固定 Ledger 计划、进程监督、证据封存和下载，
可选 MCP adapter、同 broker 维护 CLI，以及独立 Plugin 分发。具体范围和安装方式见
[实现状态](IMPLEMENTATION_STATUS.md)。旧 Task v1 的八动作不扩权。

交叉复审发现并修复：

- 封存阶段取消误清业务副作用、核对 helper 证明误替代原业务证明；未知状态继续保留资源屏障。
- 延迟启动与取消/撤权交界；实际 manager 请求在持久启动围栏中重新核验，恢复只观察原执行身份。
- 外来执行 ID 的结果、prepared 输出重启恢复和前置证据事件序；身份不合格不接纳业务输出。
- ZIP 缺少实际账本事件、未登记封存读取、并发发布及持久化失败；纳入事件/停止证明并分离文件发布与 DB 登记。
- 分块下载反复扫描全包；以受保护文件身份约束有界读取，客户端最终完整验 SHA-256。
- 完整发布身份遗漏新包及缓存漂移；四包源码固定到 Git blobs，启动前核验准确发布，生成缓存与同解释器源码编译匹配。

这些修复经过专项与最终回归；模型复审不能替代真实进程/存储环境的验证。

## D 的验证结果

环境：Linux x86_64、CPython 3.12.14。各行有独立记录，不把相互重叠测试相加。

| 验证 | 结果与证据范围 |
| --- | --- |
| 固定 D 全量源码 | **471 passed，3 skipped**；319.22 秒；3 个跳过为真实 cgroup 1 项、真实 Unix socket 2 项 |
| 新模块最终定向集成 | 172 passed，3 skipped；已包含于随后全量，使用合成 OS manager |
| 编译与 shell | tools、tests、Plugin 的 compileall 通过；bootstrap Linux shell 语法通过 |
| wheel 构建 | 固定 D，在已冻结构建环境以 `--no-isolation` 构建通过 |
| 干净基础安装 | 无第三方运行依赖；四包 39 个 payload 文件，broker/MCP 两入口身份一致；缺 MCP extra 明确拒绝 |
| 干净 MCP 安装 | 28 项已锁依赖按 SHA-256 安装；四包身份相同；pip check 通过 |
| MCP 安装态协议 | 从已安装 wheel 导入，19 项通过、0 跳过；合成签名 issuer，含真实 loopback HTTP/官方 SDK |
| Plugin 分发 | 13 成员，12 件 payload 与 D 的 Git blobs 及分发 manifest 匹配；CRC、逐件摘要及七接口摘要通过 |
| Plugin 定向 | 20 项通过；四技能校验、两份官方 JSON schema 校验通过；无真实私有连接配置 |
| 旧 S1 安装态 | 原版验收器在独立临时目录 **94 检查、292 命令通过**；原 workspace 两次 33 检查/107 命令后失败，详见下节，不抹去失败 |

28 项依赖的版本、来源摘要及许可见 [依赖清单](MCP_DEPENDENCIES.json) 与
[选择记录](MCP_DEPENDENCY_SELECTION.md)。当前锁适用 Linux x86_64/Python 3.12，
不外推其他平台。未添加本仓库许可证。

| 产物 | SHA-256 |
| --- | --- |
| `infra_local_hand-0.2.0a1-py3-none-any.whl` | `85fe4238cf0b334b4fa73820b220d1c8182c54045801fe0d7e3378619274b400` |
| 完整四包 payload | `39118e4521e4c2b01ad6740b55264cb84276b260c0faa062ebae3e46f9b83ba1` |
| `local-hand-a2-plugin-0.1.0.zip` | `8b933f95dd42a1a34478b7d8b329d7a0dbaf60b170e93202cb3bc1e9024b0c14` |
| 七接口规范摘要 | `1ff6930c4908ca4f34a563b375e28df8597de4df199a66b8c7420b17e7bf9ab3` |

Plugin 为 `UNCONFIGURED_E4_REQUIRED`；分发产物的通过不代表已在当前客户端安装、授权或接通。

## 固定 Ledger 程序的补充语义验证

固定 Ledger `6bd6acfbe5c35d581891eb87275e1173e17848fc`；254 个文件逐件核验 Git blob，
原 checkout 前后保持干净。使用真实 `ledger_jobs.build_plan` 的 prepare 六阶段固定 argv/cwd/env，
完成离线构建缓存、原位置 build/runtime venv、wheel 构建与安装。

- Ledger 源码：442 项总计，**422 通过、20 资源检查跳过**；编译通过。
- Ledger A1 安装态：25 条 CLI 调用通过。
- Ledger A2 安装态本地：**BLOCKED / UNSUPPORTED_STORAGE**，固定脚本真实拒绝当前 overlay；未修改文件系统分类或设置回退。
- Ledger wheel SHA-256：`27819cf8e6860aa49e7c3264a35a35cbb6eb3d3d3ea7774a9af4978f54b3a2ba`。
- 保留 18 条命令、36 份 stdout/stderr。普通隔离进程语义验证不代表生产 Runner 预检、硬配额或 cgroup 已通过。

以上不计入 Local Hand 的 471 项。未运行 Ledger 四专项资源套件、Python 3.11、真实 NAS 或 GX10。

## 失败记录与当前出口

开发期先行全量保留 438 passed / 11 failed / 2 skipped：重复 ZIP fixture 警告、测试客户端已弃用 API
已修复；运行期间编辑公共 provenance 文件造成一次来源不匹配，不能算不可变候选的回归。
固定 D 的全量结果另行重跑得到上表结果。最初安装验收误用未安装产品的构建解释器，
0 checks / 0 commands 失败也保留；改用干净已安装解释器后结果单列。临时目录对照首次误用带 extra 的解释器，因基础安装专用验收器要求只含 pip/产品而被拒；该次 0 检查/1 命令同样保留。
环境探针首轮错误调用实例方法，修正探针后获得实际环境事实；首轮记录同样保留。

旧 S1 原版验收在当前 workspace 两次于 `verify_installed.py:495` 失败：恢复 Worker 返回 0，
Controller wait 返回原成功 Result，但 outbox 文件又被观察为存在。保留全部现场；未删除文件重跑断言。
只读复核未找到主程序、安装核验、锁释放或 Controller 中对应的恢复路径。文件保留旧 mtime，
ctime 落在后续 Controller 调用期间；这支持调查文件可见性，但不能单凭元数据断言环境 bug。
四格恢复对照通过，两次完整前缀增加父观察后通过相关断言并主动停止（均不计完整 PASS）。
最终仅将原版验收的 run-root 改为独立 `/tmp` 路径，同一基础安装、同一 wheel、相同断言，
完整获得 **94 检查 / 292 命令 PASS**。没有修改产品或验收源码。
准确结论是目录/观察时点敏感，底层原因仍未完全确定；不能把它写成已修复或所有环境通过。
诊断中安装标记设置失败、主动停止和 strace 权限拒绝也保留，不以追踪不可用放宽验收。

| 门槛 | 状态和下一项必要工作 |
| --- | --- |
| E1 NAS 预算执行 | **实现未闭合**：服务端 nas_bytes 已有，但缺少消费该预算的真实网络配额 provider；当前永久拒绝 NAS，不算六类生产作业均已实现 |
| NAS provider 的受信事实 | 尚未冻结协议、只读查询身份、archive/账号/配额域映射与持续强制边界；不能用 statvfs、配置布尔值或本地 quotactl 冒充网络硬配额 |
| E3 真实进程监督 | **BLOCKED**：PID 1 非 systemd、无预委派进程管理准入、当前为 root；尚需隔离受限账户和真实 cgroup 故障集成 |
| E3 真实本地传输/存储 | **BLOCKED**：AF_UNIX 创建 EPERM；当前 overlay 不满足 Ledger 本地文件系统要求 |
| E4 | 未执行；实际 OAuth/私有连接、当前客户端工具发现/提交/重连及至少 16 MiB 文件交付仍需单独验收 |
| E5 / S2 | 未执行；未修改 GX10、旧服务、旧账本或恢复材料 |
| E6 | 未执行；不得以以上源码和 fixture 计数宣称真实 NAS A2 PASS |

上述 E1 代码缺口与 E3 环境阻塞分别管理。没有放宽安全约束来填补计数。
下一步是补齐 NAS provider 的准确受信输入与实现，并在具备条件的隔离 Linux 环境完成 E3；
随后才进入 E4。S2 与真实 NAS 仍按各自准确范围执行。

## 证据保留

公开仅保存本摘要和源码；原始命令、失败日志、安装态现场片段、独立复核、wheel、Plugin
保存在独立交付 ZIP，逐件 manifest 与外部 ZIP 摘要核验。原始运行日志不推入 Public Git 历史。
交付文件：`infra-local-hand-E1-E3-54d0a99-evidence-20260922.zip`。

- ZIP SHA-256：`c715f655cf6a29c680558db653eda5aaf57b49ee6c4ca33cbfe496aa7f029d88`。
- 大小 1,815,757 bytes；2,755 个 ZIP 成员；1,534 份命名为 stdout.log/stderr.log 的日志。
- 包含 23 条顶层命令记录、725 条 S1 原版/诊断命令记录及 Ledger 的 18 条记录；包含重试、失败和主动停止，不能据此计算成功任务数。
- 内含 `MANIFEST.json` 和 `SEAL.json`；核验 CRC、精确成员集合、全体成员摘要及 seal→manifest 摘要。ZIP 自身摘要在此独立记录，不宣称自哈希。
- 六份复核记录与产物一并保留；保留范围为命令/报告/诊断/状态片段，不包含虚拟环境和大型合成 Git/source fixture 副本。符号链接保存为描述数据，不在 ZIP 中制造可提取链接。

封存后仅增加本公开摘要中的外层 ZIP 身份，没有改写归档内部证据。
