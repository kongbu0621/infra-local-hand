# E1–E3 第七轮实现复核

日期：2026-09-23（UTC；保留各命令实际起止时间）。

审查输入为 `5f7e8a7ce83cec5bbb560180745a729d09e524f5`；修复源码提交 **`2be2be5203f0514ddf5108d1109fa4552cfc8bbe`**，tree **`fd55c19b2f38cf309a27bd438d16ec7a4b792196`**。本轮补充[第六轮复核](E1_E3_RECHECK_6.md)，独立保留新反例和本次验证，未沿用旧测试计数。结论仍为 **E1 有实现缺口、E3 未完成，不可部署**。

范围保持已批准的 `LH-A2-EXEC-MCP-v1` E1–E3。规则 R 为 `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，批准 A 为 `79f73faedcd9cde4164b0d1625782dae27db6c2f`，Owner 决定事件为 `LH-A2-EXEC-MCP-E1-E3-CLOSURE-20260922-01`，独立 CLOSED 登记 C 为 `367632126c1930983a06b1854f63789448633148`。执行者已直接读取固定规则、三层文档、决定副本和上轮记录。准确源码再次核对规则摘要、A 三文档原字节、B 副本自 C 起未变、C 仅含文档登记、A→C→实现祖先关系，以及生产阻断；保留副本不是对平台原始消息的独立认证。

## 已确认问题与修复

| 边界及需求映射 | 输入反例与实际影响 | 修复和保留语义 |
| --- | --- | --- |
| 预检恢复；AX-R04/R05 → A04/A05 → V04/V05 | 预检先 UNKNOWN、随后成功时，phase 已完成但 lifecycle 仍为 RECONCILE_REQUIRED；已排队核对可与后续业务重叠，或取消核对时提前删除原作业租约 | 未经重启恢复的原作业回到 RUNNING，继续持有业务阶段；recovered 分支仍 EXITED/UNKNOWN，禁止自动重放。真实 SQLite 加合成 supervisor 复现两种后果，并独立核对重开状态及完成前后取消 |
| Evidence／下载目录创建；AX-R01/R02/R04/R07/R12 → A02/A07 → V01/V02/V07/V08/V12 | mkdir 先跟随符号链接创建陌生目录，之后才拒绝 root；writer 构造和 root 被替换后的 prepare 也出现同类先写后查 | 每个缺失分量通过已打开、禁止跟随链接的父 FD 创建；prepare 先打开既有 root，再相对创建下载目录。正常读取不创建缺失目录，已存在文件和并发替换保留；不把这个局部修复称为受监督 bootstrap |
| 下载恢复清理；AX-R03/R04/R07/R12 → A07 → V03/V07/V08/V12 | binding 写入或 fsync 原始错误被关闭错误覆盖；prepare 的 KeyboardInterrupt 绕过清理，遗留拥有的描述符 | 显式记录本次主异常，局部 FD 关闭一次；prepare 对 BaseException 清理后原样抛出。验证同／新 writer 恢复及已完成文件保留，通用 writer API 不变；半写 binding 留存并在重试时拒绝，不能伪造有效绑定 |
| 认证配置获取；AX-R02/R08/R12 → A03/A08 → V02/V09/V12 | os.open 成功、fdopen 包装失败后遗留真实配置 FD | 仅在包装成功后移交所有权；失败时尝试关闭原始 FD，关闭异常不替换包装失败。未修改 JWT、权限范围或认证契约 |
| 服务退出；AX-R04/R05/R08/R12 → A01/A04/A05/A08 → V04/V05/V09/V12 | 两个入口的维护 transport 关闭失败后，后续 broker 清理未执行 | 同一清理函数逐项尝试维护服务、broker、状态和 authority；正常正文后的清理错误必须失败，有本次主异常则保持它。入口测试使用受控生命周期对象，不证明真实进程整树已退出 |
| Plugin 构建和稳定 ID；AX-R03/R04/R07/R10/R12 → A03/A07/A08/A09 → V03/V07/V10/V12 | 构建临时 FD 关闭失败跳过目录关闭并覆盖原错误；journal 清理覆盖发布错误；交叉复核另发现既有 _read/_save 包装失败遗留原始 FD | 所拥有资源独立尝试一次，只依据本次正文是否失败决定错误归属；包装失败关闭尚未移交 FD。保留已发布 ZIP、pending 文件和原稳定 ID；失败期间没有工具提交，不增加新的执行路径 |

以上按实现边界列示，同一根因的不同故障时点、重叠测试和重复运行不算额外独立缺陷。关闭错误可能发生在 OS 已释放或尚未释放资源的位置；不重试可能复用的 FD，不承诺所有关闭故障均能消除泄漏。目录与文件仍依赖受保护根和可靠文件系统，不声称抵抗任意特权并发修改或证明真实断电持久性。

## 交叉复核及失败保留

- 六个分工审查后交叉检查：runner/Ledger 对 broker，broker 对 Evidence，Evidence 对 client，auth 与 Plugin 相互检查；根执行者核对共享 S1 捕获、构建身份及整条批准／发布链。runner、固定 Ledger、contract/policy/registry/deployment 没有确认新的缺陷，未为凑修复而改动。
- Plugin 首次冻结后，独立审查发现原输入已有的 journal fdopen 获取遗漏；先保存首次源码、测试和报告，再用准确输入分别复现 read/save，协调解冻并修复，最终重新交叉核验。它属于原始缺陷；首次冻结结论由明确附录取代，不冒充首次已覆盖。
- 所有真实失败反例保留原始脚本、输入快照、摘要、stdout/stderr。失败断言之后未到达的恢复分支不倒推为已观察；原始 red 与修复后的扩大断言区分。受控 syscall、callback 和 manager 故障不冒充真实磁盘故障或实机监督。
- Evidence 私有短读夹具首次错误地要求 4097 字节按 17 字节读取时有余数，实际整除；已读取范围和字节数本来正确。修正夹具为 4099 后通过，保留原脚本与失败；不算产品缺陷。认证探针一次无效 patch 属性查找在真实调用前已捕获，随后才进入实际文件／FD 反例。
- 根执行者重复调用结果汇总时，记录器的 create-only 目录保护在启动子程序前拒绝了调用。原成功汇总、RESULTS 和日志未改写；该次外层退出为 1，无新增子命令记录，错误说明单独保留，不伪造子程序计时或退出码。此前已生成报告亦另留快照，最终审计绑定随后补充说明的版本。
- 构建使用逐项核对九个固定版本的既有工具链，新建源码工作树、基础及 MCP venv。28 个缓存 MCP wheel 重新匹配本轮冻结锁摘要并离线安装。本轮未尝试安装全新构建工具链；R6 的网络下载失败仅是历史背景，未写成本轮失败或成功。

## 准确源码与安装验证

| 验证 | 本轮实际结果 |
| --- | --- |
| 最终干净源码 | **637 PASS / 3 SKIP**；pytest `637 passed, 3 skipped in 347.62s (0:05:47)`。准确 HEAD/tree 运行前后匹配；跳过为宿主禁止两项真实 AF_UNIX transport 及真实 cgroup 不可用，不计为通过 |
| 编译、shell、来源 | Python `-W error` 编译源码、测试、Plugin 与 setup；Linux bootstrap shell 语法通过；CI 七个 Python 块另经 AST 语法检查。16 个改动路径与冻结清单一致，A 文档、依赖、catalog 和生产 guard 保持 |
| 独立构建安装 | wheel／独立 Plugin 构建通过；39 个 payload 与准确 Git blob 逐字节匹配；基础/MCP 两个全新环境安装身份前后相同，pip check 通过 |
| 本地安装态 S1 | **94 检查 / 292 命令 / 584 日志**，全通过；源码之外运行，合成 mailbox／本地 SSH shim，不是 GX10 或网络认证证明 |
| 本地安装态 MCP | **33 PASS / 0 SKIP**；外置测试副本与本次源码一致，隔离模式导入实际安装包 |
| Linux CI | **639 PASS / 1 SKIP**；源码 348.7 秒；安装态 94 检查 / 292 命令；job 634.0/900 秒，conclusion success |
| Windows CI | **198 PASS / 131 SKIP**；源码 392.4 秒；安装态 10 检查 / 10 命令；job 464.0/900 秒，conclusion success |

CI：[run 35806411316](https://github.com/kongbu0621/infra-local-hand/actions/runs/35806411316)，准确提交、push/main、attempt 1，三个 job 成功。保留完整解码日志、原始 run/jobs/steps 回应及 artifact 元数据；**未下载 CI artifact ZIP 二进制**。Windows 沿用 S1 范围，不收集 A2 jobs/MCP/Plugin 套件；各平台跳过分组和理由单独保存。CI Linux 不等于 GX10、NAS 或真实委派 cgroup 验收。

| 产物 | 大小／成员 | SHA-256 |
| --- | --- | --- |
| `infra_local_hand-0.2.0a1-py3-none-any.whl` | 186761 bytes / 45 成员 | `cedfc220efa179032ce28a453fa53ec8746b7f488f7554a15f1f664b9c4541f6` |
| `local-hand-a2-plugin-0.1.0.zip` | 18447 bytes / 13 成员 | `92c2a8411ba0e28525459ba1fbfd04735d550c9eac5190c8ddfb413fd0275bdd` |
| 安装 payload | 39 文件 | `caa04f4192beb727a001184efb5ddd7b23e0ae4c4606405e2ad59bd2c9921d19` |

Plugin 保持 `UNCONFIGURED_E4_REQUIRED`，公开 MCP 配置为空。构建通过不等于当前客户端已连接。

## 未关闭门槛

1. E1 受监督 bootstrap 尚未实现：helper 启动前目录、plan、quota I/O 的监督边界仍缺；`SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED` 无条件阻断生产。
2. E1 真实 NAS hard-quota provider 尚缺：本地计数、容量预留与 flock 不能证明 NAS 硬配额或跨主机排他。
3. E3 真实委派 cgroup 验收未完成：整树退出、延迟启动撤销、崩溃恢复和预算仍须真实合格隔离环境证明。代码缺口和宿主限制分开，不能由合成 PASS 抵销。
4. E4–E6 未执行；当前客户端私有桥、GX10/S2 切换及真实 NAS A2 均未改变，S2 仍 OPEN。旧部署、旧证据及历史未归因限制保留。

固定 Ledger 输入仍为 `6bd6acfbe5c35d581891eb87275e1173e17848fc`。六类新 job、七接口及原 Task v1 八动作不变，没有借 validation、MCP 或 Plugin 扩权。

## 私有证据与发布

完整 evidence ZIP 与独立外 seal 已保存为本对话私有交付文件，未上传 Public 仓库。

| 文件 | 大小／成员 | SHA-256 |
| --- | --- | --- |
| `infra-local-hand-A2-recheck7-2be2be5-evidence-20260923.zip` | 10770211 bytes / 1315 成员 | `0b9087bce471f0c033904582ebdada2aca81c14c32ba8d34952285944af28cf9` |
| `infra-local-hand-A2-recheck7-2be2be5-evidence-20260923.zip.seal.json` | 729 bytes / 独立外 seal | `c449a629ef63fd91aff556b9decf41429187c3f2019e57c1dc3abea15ff39681` |

封存含 **84 份结构化命令记录、292 份安装态子命令记录、754 份 stdout/stderr 日志**，另含三个 CI job 完整解码日志及 API 回应。嵌套命令和重复测试不相加为独立覆盖。RESULTS 汇总时核对 79 份记录，其后完成的汇总、报告说明及最终审计记录亦保留；重复汇总在新子程序启动前被拒绝，没有补造子程序记录。

逐成员字节、SHA-256、唯一成员集合、ZIP CRC 和 MANIFEST 绑定均通过。失败反例、原始输入快照、首次冻结版本、修复版本及夹具错误保留。最终审计脚本曾错误要求中文报告必须含英文异常名，已修正断言并保留原失败脚本和日志；这不改变产品源码或验收结果。包内包含实际使用的 28 个依赖 wheel；未打包 venv、Python 字节码或可再生的安装态合成仓库，符号链接按数据保留；CI artifact ZIP 未下载。

包内 `PUBLIC_REPORT_PRESEAL.md` 是独立事实审计绑定的封存前快照，SHA-256 `c3c577f39f3b249f96a26a332051046ce1ec20666f54b3a73eeed2de548e7ce4`，保留当时待封存状态；早先生成版本也按原摘要保留。当前报告仅在实际封存、校验和保存成功后替换本节，不回写快照或封存包。内部 seal 绑定 MANIFEST，外 seal 绑定完整 ZIP，没有 ZIP 自摘要循环。

R6 ZIP 与外 seal 已再次核对摘要不变。私有规则原文、机器／工具原始信息和日志只在私有证据中保留；公开仓库只提交修复、回归测试及脱敏报告。修复源码与报告分别提交；本次报告提交仅改本报告、README 和实现状态导航，已验源码保持原字节。

摘要完整性不等于来源签名、真实断电持久性或 GX10/NAS 验收。E1 代码缺口、E3 真实验收及 E4–E6 边界保持。
