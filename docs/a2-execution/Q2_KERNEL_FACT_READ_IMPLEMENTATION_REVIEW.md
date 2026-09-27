# Q2 固定内核事实读取：实现与交付复核

本轮按 Owner 已批准的 `LH-Q2-KERNEL-FACT-READ-v1` 实现本地预检的两项固定
内核视图读取。K1 实现、K2 开发环境与真实普通身份验证、K3 准确 RAM 包均已完成；
K4 等待原 host 的完整 JSON。
这项进展不关闭 Q2 验收，不证明 H07、联合账单、消费资格或完整执行条件。

## 批准链与准确实现

| 层级 | 准确记录 |
| --- | --- |
| R | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，规则采用关系沿用根 `AGENTS.md` |
| A | `887b640b394f9983f37dfe97c58ba35aaa099359`；[准确三文档](q2-kernel-fact-read/REQUIREMENTS.md) |
| B | 2026-09-27 23:41:45 +08，Owner 批准准确 A/范围、关闭 Gate，并明确同意本轮脱敏结论、方案及登记文档推送至公开仓库；[准确决定副本](../governance/Q2_KERNEL_FACT_READ_OWNER_DECISION.md) |
| C | `f7f8b503470725ca1ba18d1cb8d8b39e09a15ea8`，只含独立关闭登记 |
| D | `e15c633adbdfbf1e29cb12b2410975fe4911458d` |
| D tree | `c7c60ec47b742615dbae9f8cb230679f3a9c4997` |

D 以 C 为直接父提交。A 的三份文档以及原 host A
`8402f0cc82d8a0ac0b9a56716bf276f41cafea37` 的三份文档均经 Git 原字节比较，
未被改写；其历史 OPEN 标签保留准确的批准前状态，不取代后续独立 C。
原 startup、对账与 host 批准链、冻结 runtime、旧 boot pin 和预算保持。

本轮变更为新增 `q2_host_kernel_facts.py` 及其定向测试，并接入原
`q2_host_window_preflight.py`、调整对应测试。普通证据 IO、接收器、消费组件及
runtime 原字节保持。此前权限阻断截图及旧包继续保留，没有改称成功。

## 两项读取的资格与限制

专用入口只接受内部 `boot` 或 `mountinfo` 枚举，对应固定 boot 视图和由
`os.getpid()` 取得的自身 PID mountinfo；不接受路径、外部 PID 或降级开关。
资格检查不依赖先读取 mountinfo 的内容。

| 环节 | 实现与拒绝条件 |
| --- | --- |
| ABI | 限 Linux x86_64 LP64；检查结构大小、偏移、整数宽度及符号；原生 `fstat/fstatvfs` 与 ctypes 结果交叉核验，未知或不一致即拒绝 |
| 名称与 fd | 根、祖先与叶项逐段 `O_PATH/O_NOFOLLOW` 持有；检查目录/普通叶类型、root/当前 euid、保护 mode 与叶项单链接 |
| proc 绑定 | 对 proc 及其下每个 fd 验证 `PROC_SUPER_MAGIC`、设备及同一挂载 ID；要求 `statx` 返回 mask 包含所需位，子挂载或身份变化拒绝 |
| 内容读取 | 只对这两个固定叶项使用普通只读、no-follow、nonblock；读前比较内容 fd 与 held 叶身份，并复核完整名称链；无 PermissionError 后去掉标志重试 |
| 读取界限 | boot 至多 64 bytes，mountinfo 至多 1 MiB；有界分块读和 EOF 检查，每步检查原双钟；读后复核 fd、挂载、名称链与保护身份 |
| 错误与清理 | 固定操作/目标标签、准确 errno；保留最后元数据与已取得的读后观察；异常和 deadline 均关闭已取得 fd，不重试 close |
| 报告 | 资格要求与实际完成数量分开；读前全部合格后才记录 `qualified_before_content`，读后全部通过才记录 complete；只返回部分观察或阻断 |

报告明确将原 host 终端与 proc/PID namespace 对齐标为
`ENVIRONMENT_ASSUMPTION_NOT_PROVEN`。procfs magic、挂载 ID、数字 PID 或 boot
匹配均不能单独证明该对应。本轮没有为了证明它而增加其它 proc 读取或进入 namespace。

这两个内核视图的访问/动态元数据可以变化，报告保留可得的前后元数据与内容摘要；
这不构成历史元数据保全证明，也不回写时间戳。设备/inode、挂载、类型、owner、
mode、nlink 的身份漂移仍拒绝。普通证据文件及目录枚举继续使用原
`O_NOATIME` 和原有完整性核验，不进入该例外。

## 验证结果及适用范围

开发环境受影响整组实际结果为 **331 PASS / 3 SKIP，17.50 秒**，
见[原始测试输出](evidence/q2-kernel-preflight-20260927/component-tests.txt)与
[验证索引](evidence/q2-kernel-preflight-20260927/validation.json)。
其中两项 SKIP 为既有环境限制；新增真实普通身份 fixture 在隔离子进程降为普通
身份时返回 errno 22，明确记录 SKIP，没有以 root 或 mock 结果替代。

专用读者的 37 个通过项覆盖：任意目标、未知 ABI/缺符号、非 procfs、子挂载、
缺 statx mask、ABI 交叉核验失配、symlink/hardlink/可写或错误类型、名称替换、
同 inode 新挂载、读后身份变化、动态元数据披露、两项长度边界及 +1、短读至 EOF、
准确 syscall/errno、不同阶段 deadline 和 fd 清理。原预检测试继续检查普通
证据拒绝降级、错误 boot、原接收起点到期、无消费/派发与新增批准声明缺失。

合成 proc 测试替换定位根和 procfs magic，并使用真实 fd 与原生 ABI；
它们证明拒绝逻辑，不证明原 host 的 proc、身份或 namespace。
开发环境原生 ABI 元数据核验通过，也不能代替真实普通身份成功。

**真实普通身份 CI 已通过。** 在隔离的 GitHub Actions runner 上，准确 D 的专用
读者以 **euid 1001** 实际读取 boot **37 bytes**、自身 mountinfo **2,502 bytes**，
两项均完成读前资格和读后核验；对应原生交叉核验数量为 32 / 22。
同一普通身份的普通 `O_NOATIME` 对照读取返回 **errno 1（EPERM）**；这记录了
本次权限边界，不宣称已枚举全部进程能力。准确源码 SHA-256 为
`947469560ca3bdc4997a56739b42561c4a616a5dc8b250b919db589689eecc02`。
CI 同时核验包含 A/登记/C/D 的 4 个准确提交与 12 个变更文件。

见[普通身份证据](evidence/q2-kernel-preflight-20260927/ordinary-identity-ci.json)及
[实际 CI 作业](https://github.com/kongbu0621/infra-local-hand/actions/runs/36331366647/job/108653819147)。
这项成功补齐 K2 的隔离普通身份验证，不改写前述云环境的 3 项 SKIP，
不证明原 host 的 ABI、权限、boot 或 namespace 对齐，也不能代替 K4。

### 通用 CI 的既有失败另行保留

发布合并 M `ad405506abf46952f271f3fb309ed7bd873e3d1c` 的通用 CI
[run 36331451304](https://github.com/kongbu0621/infra-local-hand/actions/runs/36331451304)
实际未通过：Linux 源码测试为 **21 FAILED / 2,140 PASS / 31 SKIP，457.50 秒**；
Windows 为 **6 个收集错误 / 7 SKIP**，涉及 Linux `/proc`、`fcntl`、`termios`。
前序 D `0a456a909821fd1fc6a4fdec43b9e16bc88679f2` 的
[run 36324126279](https://github.com/kongbu0621/infra-local-hand/actions/runs/36324126279)
已存在同样 21 个 Linux 失败测试与同样 6 个 Windows 收集错误；该次 Linux 为
2,095 PASS / 31 SKIP。本次未增加失败测试标识，但完整 CI 仍为失败。
Linux 失败集中在既有受保护采集、旧 backend 内核读取和预检测试；其中部分
预检测试实际返回 `HOST_LOCAL_ACL_PRESENT`。不能因局部测试或新专用读者成功
而忽略这些结果。
见[平台结果与前序对账](evidence/q2-kernel-preflight-20260927/ci-platform-status.json)。

上述失败作为未解决的验证缺口保留。K2 的专用读者实际普通身份验证和本地
定向验证分别按其环境记录；本复核没有作出“全仓库 CI 通过”或原 host 可执行
完整 Q2 的结论。

## 准确 RAM 包与交付验证

新包 `q2-kernel-preflight-20260927.pyz` 固定上述 D/tree，准确长度
**5,609,648 bytes**，SHA-256：

`04af4262c6ea033862512d05df68ff5665498023660ce312c57f956ecda9a616`

两次独立组装逐字节一致。离线验证在工具编译/导入前核验 D/tree、全部
**49 个工具 Git blob**、原三条批准链和新增第四条批准链；新 A 三文档、准确 B
及 C 的登记文件同时绑定摘要与 Git blob，确认 D→C→A 顺序。
离线来源验证为 **47 个 typed sources / 48 个 blobs**；它们与 49 个工具计数口径不同。
旧私有原件 pin、冻结 runtime/tree/wheel 均未采用新值，包不含 runtime tar。

**17 个拒绝负例全部通过**：包括改工具并重算 index、删除 C/A、削弱批准列表、
修改 A/B、扩大核准对象、旧包套用新例外、改原始 host 输入、增加 ZIP 成员、
超大 index、缺接收起点、直接磁盘 local 模式及执行模式。
见[脱敏包验证](evidence/q2-kernel-preflight-20260927/package-validation.json)。

准确启动命令 9,190 bytes，完整输入帧 7,494,251 bytes，合计
**7,503,441 bytes < 16 MiB**。启动 argv 与帧解码已分别复核；外部完整包 SHA、
接收器原字节及包内 Git 证明共同约束实际执行内容。
见[准确交付验证](evidence/q2-kernel-preflight-20260927/exact-delivery.json)。
16 MiB 是传输输入界；解压后成员约 14.4 MB，不应与 ZIP wire bytes 或普通证据
读取预算混用。host 的实际内存峰值未据此证明。

完整新帧在当前云工作环境真实 PTY 的最终原点核验耗时 **4.076 秒**，
退出码 2，在 `host_boot` 阶段返回 **`HOST_LOCAL_KERNEL_MOUNT_CHANGED`**。
该环境存在 proc 子挂载，按合同拒绝。完整帧已发送，载荷未回显，终端属性恢复，
报告中的两项原点均早于载荷发送，原最早起点未刷新。
见[PTY 与原点证据](evidence/q2-kernel-preflight-20260927/workspace-pty-origin-check.json)。

该 PTY 测试未连接原 host、guest，未消费窗口或发行 owner；它是开发环境的
真实拒绝测试，不是原 host 预检成功，也不能替代先前截图或未来 K4 原始 JSON。
原 140 秒准备界与 300 秒双钟总界保持，时间包含输入接收、验证及本地观察。

## 当前收口与下一步

| 阶段 | 当前状态 | 仍需取得的证据 |
| --- | --- | --- |
| K1 专用读者与接入 | 完成 | 准确 D 已固定 |
| K2 验证 | 开发环境与准确 D 的真实普通身份 CI 完成 | 原 host 条件由 K4 单独观察；开发环境 SKIP 保留 |
| K3 准确包 | 完成 | 包、启动命令及输入帧保持同一固定版本 |
| K4 原 host 验证 | 待完整 JSON | 原已有终端、原普通账号、既定环境假设下的真实结果 |

原 host 使用新包后可能继续因身份、boot、保护、原件或后续事实缺口阻断；
应原样保留结果，再判断下一缺项。无须为同一已批准局部范围重复批准，也不应
为取得正例提权、改 owner/mount/能力、替换 boot pin 或放宽普通证据保护。

H07 首次远端有效期限、完整费用与原生审计、wrapper 来源及执行绑定、文件系统
持久资格仍分别缺证。未知费用不填零；本地部分观察不产生联合准入。原唯一
未发行批次、历史未完整结果及相关义务继续保留。

公开材料依据本次准确 Owner 决定，仅含代码、脱敏结论、方案和验证登记；
真实机器路径/boot、截图、私有载荷与原始输出另行私有保留，不加入公开证据目录。

准确 A/C/D 的公开发布证明见[发布验证](evidence/q2-kernel-preflight-20260927/publication.json)。临时导入提交与准确 D 通过双父合并保留，合并 tree 与 D 完全相同；当前树已移除临时导入文件，未强制更新引用。
