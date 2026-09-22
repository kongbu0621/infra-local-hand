# E1–E3 第四轮实现复核

日期：2026-09-22（UTC；实际命令时间分别保留）。

审查输入为 `23a575473b3aab33ef2e80d03808aec79046ede8`。最终修复源码为 **`1921ea14bf241544539b18e8bbbe7a0b5d0c7908`**；tree：`c2841adc06d47a1bb15dfaf36a79b11a22ef785f`。初始候选 `11225c1072d4490ecfa59c0431ae7d424d673b58` 在 Windows CI 失败，由后续修复提交取代，其失败与已通过的局部验证均保留。本记录补充[第三轮复核](E1_E3_RECHECK_3.md)，各候选验证独立记账。结论保持 **E1 有实现缺口、E3 未完成，不可部署**。

范围仍为已批准的 `LH-A2-EXEC-MCP-v1` E1–E3。固定规则 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 本轮重新读取并核验摘要；批准 A `79f73faedcd9cde4164b0d1625782dae27db6c2f` 的三层文档保持不变，独立 CLOSED 登记 C `367632126c1930983a06b1854f63789448633148` 保持为实现祖先，准确候选已保留逐字节及祖先链路核验记录。Owner 继续修复及直接 main 发布授权保持；没有修改权限、依赖、作业类型、生产阻断或真实部署配置，R → A → B → C → D 顺序保持。

## 已确认问题与修复

| 边界及需求映射 | 已证实问题 | 修复及限制 |
| --- | --- | --- |
| 业务结果与证据恢复；AX-R04/R07，AX-V04/V07/V08 | 业务已持久确认 SUCCEEDED/FAILED 后，等待封存、封存 helper 未决或封存失败已退出时，`recover()` 仍把业务结果改为 UNKNOWN；已退出阶段没有后续观察可恢复该结果 | 在封存生命周期中保留已冻结 `business_outcome`；当前证据 helper 仍标 DURABILITY_UNKNOWN 并重查退出证明。独立复核另补齐恢复后新证据启动因策略代次被拒绝的 `_unknown` 路径；未创建证据意图时保持 STAGING。真实业务意图仍 UNKNOWN，不重跑、不释放未证明的资源、不开放 prepared 输出 |
| EOF 与执行预算；AX-R02/R04/R07，AX-V04/V07/V08 | 固定程序先关闭 stdout/stderr 再继续工作时，捕获循环因 EOF 结束，短暂 wait 后提前杀死仍有预算的直接子进程 | 只要仍有 pipe 或原直接子进程未退出，就继续使用既有墙钟预算；超时仍触发受控终止及有限排空。真实子进程反例通过；不把直接子进程退出替代 cgroup 证明 |
| 有界 plan/result 读取身份；AX-R01/R04/R07/R10，AX-V01/V04/V07 | 父目录换位后，持有 FD 的元数据可以保持不变，读取函数仍返回已经脱离当前命名路径的旧结果 | 对读取前后 FD 和最终命名条目比较完整身份，包括设备、inode、类型、链接数、所有者、大小和时间信息；检测到变化拒绝，保留替换文件；大小上限、no-follow 及非阻塞特殊文件拒绝保持 |
| 保留 wheel 的验证与摘要；AX-R10，AX-V01/V10 | ZIP 验证结束后重新按路径读取并返回摘要；在两步之间对同 inode 追加未登记 import 成员，仍可能返回变更 wheel 的成功摘要 | 同一普通文件 FD 覆盖 ZIP 成员验证与有界摘要读取，结束核对 FD 及当前命名路径完整身份；检测到变化拒绝，不删除产物；保留原有链接路径语义与受保护目录前提 |
| 下载完成后的最终持久化身份；AX-R07/R09，AX-V07/V08 | final 已验摘要后，文件或目录 fsync 期间发生同 inode 改写并恢复大小/mtime，最终仍可能成功返回；新下载和已有 final 恢复都受影响 | 最终 FD 持有至文件、下载目录、私有根同步与绑定检查结束，再与验摘要时的完整身份比较；命名条目也在退出时复核。变化返回 CONFLICT，保留文件，不覆盖或删除；恢复仍复用同一 artifact |
| Plugin 请求日志的父目录持久化；AX-R03/R04/R07/R09，AX-V04/V07/V08 | 新建 journal 仅同步文件及 journal 本身，没有同步父目录；请求 ID 已报持久、甚至用于 submit 时，journal 的目录条目持久性仍未确认 | 固定父目录身份，经父 FD 打开 journal，并在原 ID 返回或发送前同步父目录；失败返回 IO_UNCERTAIN，原文件保留、健康重试复用原 ID。独立复核另修复首次修补加入的 fsync 后回读窗口，见下节 |
| Evidence 私有根创建链持久化；AX-R07/R09，AX-V07/V08 | 自动创建多层私有根时，仅同步根本身不足以确认各祖先目录条目持久性；父目录同步故障下，writer 仍可能误报下载成功，store 仍可能登记产物 | 从 `/` 逐级以 no-follow 打开并保持目录 FD，逆序 fsync 并核对父子 dev/inode。writer 将该同步包含在 final FD 最终身份检查内；store 在最终 artifact 身份检查与登记前完成。失败保留发布残留，store 不登记、不开放读取；writer 健康重试复用同一 artifact，不重取 ZIP |

第七组 `artifact-root-ancestry-red` 已保留 2 FAIL，修后 `artifact-root-ancestry-green` 为 50 PASS；覆盖新建多层父目录/祖父目录同步故障及 writer 同 artifact 恢复。它是确定性的 fsync 边界故障注入，**不是实际断电实验**；未宣称 store 的原 seal 自动恢复通过。独立 contract 复核 4 项定向检查及 2 个额外探针通过，覆盖祖先 fsync 期间同 inode 改写与目录祖先替换，失败残留保留。

上述文件检查针对返回前已观察到的变化，不承诺抵御返回后任意高权限改写。受保护目录、文件系统 fsync 语义和真实进程监督的前提保持。

## 多路复核、反例及失败分类

本轮分路检查 broker/状态/资源、runner/固定 Ledger、认证/MCP/维护入口、证据/下载、契约/策略/Plugin；保留 wheel 另有实现及独立复核。交叉复核覆盖 broker 的封存生命周期、runner 的 EOF/预算和路径绑定、下载的最终同步、Plugin journal、wheel 验证与摘要。真实 SQLite、文件系统、子进程、密码学和 HTTP/SDK 与合成 supervisor、issuer、回调分别记账。

- **基线反例。** broker 原始六个子例均失败；下载的两个测试分别在第一个文件 fsync 子例失败，不能把计划中的六个边界都写成已独立观察到的基线失败。后续最终测试确实覆盖文件、下载目录、私有根三个同步点 × 新建/恢复两条路径。wheel 使用真实 setuptools 产物及真实 ZIP 修改，注入的是时序边界。
- **初步未复现的探针。** runner 最初的单文件 rename 探针被原实现通过 ctime 变化拒绝，因此没有计为缺陷；随后父目录换位才确认命名路径与 FD 脱离。保留前一次结果，不混写为全部探针都复现。
- **验证器调用失败。** runner 一次定向命令使用包含 `..` 的相对解释器路径，三个既有 canonical-path 准入测试正确拒绝；改为绝对解释器后通过。原命令 3 FAIL / 35 PASS / 1 SKIP 保留，不冒充产品回归或最终通过。
- **并发审查观察到另一条 red。** 名为 `artifact-final-sync-green` 的早期宽范围命令实际为 1 FAIL / 76 PASS，失败来自当时仍在修复的 Plugin 父目录同步测试。该日志保留，不能把命令名当作通过结果。
- **修复期新增窗口。** Plugin 初版把新增父目录 fsync 放在身份文件已检查并关闭之后；该阻塞点内的同 inode 改写可能使实际 journal 与提交 ID 不一致。独立反例先失败，最终保持身份文件 FD 跨过全部同步屏障，再核对 FD 和命名条目，包括 ctime；改写残留保留，submit 回调不触发。这一新窗口属于修复期问题，不写成输入候选已有该同步步骤。
- **跨审补齐同一缺陷链。** broker 最初保住 `recover()` 的业务结果后，独立检查发现后续证据启动被当前策略拒绝仍可能经 `_unknown` 再丢结果；最终同一生命周期修复覆盖该路径。独立 red 命令意外同时发现导入的既有测试，共 40 个方法、仅独立方法两个子例失败；最终独立 green 明确只执行该方法及三个结果子例，不虚增独立检查数。
- **最终构建器调用失败。** 最终候选的 Plugin 首次构建因未预建输出目录被拒绝，第二次因 wheel 构建已生成源码树内的 `build/` 内容，被来源完整性检查拒绝。两次均为隔离验证流程错误，保留非零退出和日志；修正输出目录及构建顺序后，以新的记录标签执行，没有弱化构建器检查。最终成功以准确候选结果为准。
- **修复期 Windows 回归。** 初始候选 `11225c1` 新增的 `Path.stat()` 与 `os.fstat()` 完整 tuple 比较，在真实 Windows CI 使两个 wheel 测试提前拒绝。CPython 3.12.10 固定源码显示两个 Windows API 的 ctime 语义可不同；原 CI 未打印各字段，未声称直接测到了某一字段的差值。最终候选通过再次打开当前命名文件，用两端 `fstat` 比较完整身份，保留 ctime、dev/inode、同 FD 验证与有界摘要。辅助打开在 POSIX 使用非阻塞选项，命名文件被换成 FIFO 时及时拒绝。新增跨 API 时间语义回归先失败、修后通过；独立健康摘要、命名替换、原验证文件流关闭失败和真实 FIFO 探针均通过。没有删除断言或跳过失败测试。

各命令保留实际 argv、时间、退出码及独立 stdout/stderr 摘要。初始部分只读源码查看只有工具记录，没有事后补造精确时间。定向检查来自当时审查工作树，以下数字不能替代冻结候选的完整验收，也不能简单相加。

| 定向范围 | 已完成结果与边界 |
| --- | --- |
| Broker、policy、resources、contract | 最终 80 PASS / 0 SKIP；新增一个 pytest node 内含九个恢复状态组合，另检查重复恢复、策略拒绝、无重跑、资源屏障；独立复核一个方法通过 |
| Runner、固定 Ledger helper | 38 PASS / 1 SKIP；绝对解释器、warnings-as-errors；真实 cgroup 集成仍跳过。三项新增回归经交叉复核 3 PASS / 0 SKIP |
| Auth、MCP server、维护 CLI | 52 PASS / 1 SKIP；宿主禁止真实 AF_UNIX，真实 loopback HTTP/SDK 通过。独立合成 issuer 接受 ES256/P-256、拒绝错误曲线；七工具 × 六种无效参数均 HTTP 400，共 42 次，broker 调用为零。该面未确认新缺陷、未改源码 |
| Evidence store/client | 补齐私有根创建链后 50 PASS / 0 SKIP；此前最终文件同步的独立检查 6 PASS / 0 SKIP。新增祖先同步链独立 4 项定向检查及 2 个探针通过；最终范围仍以下述冻结候选验证为准 |
| Contract、policy/registry、Plugin | 最终 65 PASS / 0 SKIP，包含修复期回读窗口回归；早期 64 PASS 不作最终闭环依据 |
| Build identity、deployment / retained wheel | 最终 31 PASS / 0 SKIP；原修改后摘要错误及新增跨 API 时间语义回归均先失败后通过；独立验证健康摘要、命名替换、原验证文件流关闭失败及辅助打开遇 FIFO 均符合预期 |
| 固定 Ledger 只读映射 | 固定提交、两个 Git blob、构建版本、六类作业/四资源变体、八个 NAS 前置证据槽、资源租约、临时根及无凭据环境映射通过。上游资源测试 8/1/7/4 的数量来自语法检查；**没有新执行这些上游完整套件或 NAS roundtrip** |

## 准确冻结候选验证

初始 `11225c1` 本地源码为 583 PASS / 3 SKIP，基础安装态为 94 项检查、292 条命令，MCP 安装态为 30 PASS / 0 SKIP；但 [CI 35769636440](https://github.com/kongbu0621/infra-local-hand/actions/runs/35769636440) 总体 **FAIL**：Linux 585 PASS / 1 SKIP，Windows **2 FAIL / 194 PASS / 125 SKIP**，Windows 后续安装步骤未执行。这些结果不能替代下表最终 `1921ea1` 的验收。

| 项目 | 准确结果 |
| --- | --- |
| 源码提交 / tree、独立工作树前后状态 | **PASS**；`1921ea14bf241544539b18e8bbbe7a0b5d0c7908` / `c2841adc06d47a1bb15dfaf36a79b11a22ef785f`，源码测试及构建分别使用独立工作树；测试前后准确 HEAD/tree 且干净 |
| 全量源码测试、Python 版本、耗时、全部跳过原因 | **584 PASS / 3 SKIP**；Linux x86_64、Python 3.12.14、pytest 8.4.2、`-W error`，pytest 346.57 秒，进程 347.527 秒，退出 0。两项真实 AF_UNIX 因宿主策略禁止而跳过；一项真实 cgroup 因 bootstrap 未实现、PID 1 非 systemd、无预委派 manager 及所需专用非 root 账户条件而跳过。全部原始理由和日志哈希保留 |
| 编译、shell 语法、wheel 与 Plugin 构建 | **PASS**；独立干净源码树、既有准确冻结的构建工具链，源码/测试编译、shell、wheel 及最终 Plugin 构建通过；Plugin 两次流程错误另行保留 |
| 全新基础安装态 S1 检查、命令及日志核验 | **PASS**；94 项检查、292 条命令、584 份日志，250.806 秒。逐条核对预期退出码、capture_complete 与日志摘要；外层命令另核对日志大小及摘要。使用新的 `/tmp` 合成环境，未操作真实节点 |
| 冻结依赖的 MCP 安装态、入口及 payload 一致性 | **30 PASS / 0 SKIP**；全新 MCP 环境、哈希锁依赖、外部逐字测试副本，`-I -W error` 执行已安装产品。两环境 `pip check` 通过，39 个 payload 文件与准确源码绑定。依赖安装一次代理超时后重试成功，警告保留。基础安装身份在 S1 运行中及完成后取样，MCP 身份在测试前后取样；不把运行中快照写成 S1 启动前快照 |
| Linux / Windows 准确提交 CI、原始日志、适用范围与预算 | [run 35771436119](https://github.com/kongbu0621/infra-local-hand/actions/runs/35771436119)，准确 `1921ea1`、push/main、attempt 1，整体 **success**。Linux 586 PASS / 1 SKIP、源码 336.87 秒，安装态 94 检查 / 292 命令，job 609/900 秒；Windows 197 PASS / 125 SKIP、源码 248.60 秒，安装态 10 检查 / 10 命令，八项 Windows 专用步骤通过，job 299/900 秒。三个 job 全部成功，无重跑、无超时；保留全部 job 原始日志、逐步结论及 artifact 元数据 |
| A 三文档逐字节、C 祖先、公开差异及批准链核验 | **PASS**；A 三文档原字节及 SHA-256 不变、C 为祖先；准确 14 文件差异和有限凭据模式扫描通过，7 个 workflow Python block 的 `ast.parse` 语法检查通过。模式扫描不构成穷尽秘密保证 |

Linux CI 唯一源码跳过为真实 systemd/cgroup 集成，包含 `SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED`、未预先委派 manager 及所需专用非 root 账户条件。Windows 不收集 A2 jobs/MCP/Plugin 套件，125 项跳过的分组位置及原始理由全部保留；其结果只支持现有 S1 Windows 平台范围，不证明 Windows A2 可用。CI artifact ZIP 二进制未下载；本包保留 API 元数据和完整解码 job 日志，不能把元数据称为 artifact 原件。

| 最终产物 | 大小 / 成员 | SHA-256 |
| --- | --- | --- |
| `infra_local_hand-0.2.0a1-py3-none-any.whl` | 183881 bytes / 45 ZIP 成员 | `9c1f1039b3052992a84e762921d20f10c8cdf98ec3c8bb3e49d0be3d315afef4` |
| `local-hand-a2-plugin-0.1.0.zip` | 18249 bytes / 13 成员 | `e12fb1bbad20f0ba0151aaef6731edd0149489b2670774fefde9215d3855ad36` |
| 安装 payload | 39 文件 | `ac4250ba92c4e7e4e2c6dab410869ef97d49434f50b39bcd0535c2e57358a24c` |

Plugin 保持 `UNCONFIGURED_E4_REQUIRED` 与空公共 MCP 配置；构建通过不代表已完成 E4 接入。

## 未关闭门槛

- **E1 受监督 bootstrap 尚未实现。** helper 启动前目录、plan、quota I/O 的独立监督边界仍缺，`SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED` 生产阻断保持。本轮进程预算和结果绑定修复不关闭该缺口。
- **E1 NAS hard-quota provider 尚缺。** 未增加生产 provider；有限本地预算、映射和合成验证不证明真实 NAS 配额。
- **E3 真实委派 cgroup 验收未完成。** 真实进程树、延迟启动撤销、崩溃恢复与预算尚未证明。该跳过同时包含代码缺口及宿主条件，不能全部归因于环境或以合成 PASS 代替。
- **E4–E6 未执行，也不在本轮范围内。** 当前 Work 实际交付桥、GX10/S2 切换、真实 NAS A2 尚未验收；S2 仍 OPEN，旧部署和历史证据不变。
- **历史异常仍保留。** S1 workspace outbox 异常未归因；第二轮 CI 清理失败的具体写入者未直接采样。本轮新通过不能倒推这些历史限制已关闭。

## 私有证据及发布

完整 evidence ZIP 与独立封存记录均已保存成功，作为当前对话的私有交付文件；未上传至 Public 仓库。

| 文件 | 大小 / 成员 | SHA-256 |
| --- | --- | --- |
| `infra-local-hand-A2-recheck4-1921ea1-evidence-20260922.zip` | 1977555 bytes / 2246 成员 | `556114fa9bfaac097011840371599107cc21e2065827e73c6dae62691f32bbb8` |
| `infra-local-hand-A2-recheck4-1921ea1-evidence-20260922.zip.seal.json` | 独立外 seal | `4e01e770af9c2f9d0d5f8b1ef267ed80335714de708dd4112fb0e1ae60d778d2` |

封存包含 107 份结构化验证记录（含外层及单独记录的子命令，不是互不重复的测试数）、两轮候选共 584 份安装态子命令记录（各 292）、1382 份 stdout/stderr 日志，另保留两轮 CI 的全部六份 job 日志与 API 回应。CRC、唯一准确成员集合、逐成员字节及摘要、MANIFEST 绑定全部通过；失败反例、修复期回归、验证器错误和后续通过记录均保留。

包内 `PUBLIC_REPORT_PRESEAL.md` 是独立最终事实审核绑定的封存前快照，SHA-256 为 `42d1ffd4dfe4d4c5a6750dd386d4379481c44856e23c742326a8b2cd2261db00`，明确保留当时待定的封存字段。本公开报告在实际封存及保存成功后补齐本节，不回写该历史快照。内部 SEAL 绑定 MANIFEST，独立外 seal 绑定 ZIP；没有 ZIP 自摘要循环或数字签名声明。

最终公开报告只包含修复源码、测试与核实后的摘要；私有 Gate 原文、原始日志、失败探针及现场材料不进入 Public 仓库。封存已保留输入候选 red、修复期失败、验证器失败、交叉检查和准确候选记录，并明确排除虚拟环境、缓存及可再生的安装态合成仓库内容。源码提交与报告提交分开；任何 seal 摘要都不等于数字签名或 GX10 实机证明。
