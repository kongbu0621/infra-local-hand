# E1 NAS 只读配额适配：合同与剩余准入

本说明记录既有 E1–E3 授权内的内部实现，不修改已批准的三份 A 基线文档、不增加公开 job 参数，也不授权真实 NAS 访问。实现位于 `tools/local_hand_jobs/nas_quota.py`，专属测试为 `tests/test_local_hand_jobs_nas_quota.py`。

**当前没有可执行的真实 NAS 配额 provider。** 已实现的是 `smbcquotas-user-v1` 的固定请求构造、响应解析和带身份／时间绑定的逻辑验证。`execute_live_queries()` 无条件返回 `UNSUPPORTED`；配置、布尔声明和成功 transcript 均不能打开入口。runner 的 NAS 封堵、capabilities 以及 `E3_SUPERVISION_UNVERIFIED` 不因本模块改变。所有成功验证结果固定标记 `coverage=LOGIC_ONLY`、`business_authorized=false`。

## 1. 固定上游依据

输出格式依据 Samba **4.23.0** 的完整 commit `942092eadf52c46f9bd913525015d53cb1cc8fb1`，不是从手册推测。此版本仅是本次解析合同的源码基线，不代表已选择、安装或验证任何生产二进制。

| 固定上游文件 | Git blob | 采用事实 |
| --- | --- | --- |
| [source3/utils/smbcquotas.c](https://github.com/samba-team/samba/blob/942092eadf52c46f9bd913525015d53cb1cc8fb1/source3/utils/smbcquotas.c) | `b9bbb0f01853724d26a67bc321d3a7140e8da313` | `dump_ntquota` 的 numeric/verbose 输出；`StringToSid` 接受数值 SID；`do_quota` 的错误与退出语义 |
| [source3/libsmb/cliquota.c](https://github.com/samba-team/samba/blob/942092eadf52c46f9bd913525015d53cb1cc8fb1/source3/libsmb/cliquota.c) | `865a41ff6188600defd5050c28016bda7a58ed50` | 返回记录的 SID、用量、soft/hard 数值进入解析结果 |
| [source3/include/ntquotas.h](https://github.com/samba-team/samba/blob/942092eadf52c46f9bd913525015d53cb1cc8fb1/source3/include/ntquotas.h) | `6fbbbb9ae5f35890018a13dcdc1caf64326963df` | `2^64−1` 为 NO_LIMIT、`2^64−2` 为 NO_ENTRY、0 为 NO_SPACE；启用与强制执行为不同标记 |

固定 numeric/verbose 用户响应有四行：SID、used、soft、hard。文件系统响应有九行，包含默认 soft/hard、启用、Deny Disk 和两项日志标志。解析完整 ASCII 输出，允许数值前的空格；拒绝缺行、重复、额外文字、非十进制数、负数、前导零、非 ASCII、截断和超出 4096 字节的输出。所有字段名称、顺序、换行和 On/Off 大小写须匹配。

上游有一个必须覆盖的特殊情况：服务器不支持 quota 时，`do_quota` 输出不支持提示，却返回 0。因此 exit 0 本身绝不构成配额证据；stderr 非空也保守拒绝。numeric 模式输出无符号数；显示函数的非 numeric 0 值文字不能当作配额语义。有效硬上限必须大于零、有限且不超过 `2^53−1`，上述特殊值均拒绝。首版同样保守拒绝为零或无限的默认 soft/hard 和用户 soft 值，不自行补用默认值。

本模块没有复制、打包或安装 Samba 源码／二进制，也未增加 Python 第三方依赖。将来实际工具及其动态依赖、配置加载面、许可证和构建来源仍须冻结；固定这三个源码 blob 不能替代二进制来源核验。

## 2. 纯内存 API 与准确绑定

| API | 当前行为 |
| --- | --- |
| `validate_admission(admission)` | 严格核对声明结构并返回副本；不读取配置、可执行文件、挂载或凭据 |
| `build_query_requests(admission, context)` | 构造恰好 filesystem/user 两个顺序只读请求及各自规范摘要；不执行 |
| `parse_filesystem_response(bytes)` | 解析完整响应，要求 Quotas Enabled 和 Deny Disk 都为 On |
| `parse_user_response(bytes, remote_sid=…, nas_bytes=…)` | 核对返回 SID 与有限总硬上限；不把可用空间冒充硬上限 |
| `validate_responses(admission, context, observations, now=…)` | 核对两次响应、执行身份、前后绑定与新鲜度；仅返回逻辑验证结果和摘要 |
| `execute_live_queries(admission, context)` | 始终抛出 `JobError("UNSUPPORTED", …)`；无文件、进程、凭据或网络 I/O |

下面是模块内部合同；**不是当前 Policy 已接纳的新配置字段**，也不应直接加入生产 profile。每个对象拒绝未知字段。

| admission 字段 | 声明与限制 |
| --- | --- |
| `provider` | 固定 `smbcquotas-user-v1`；不隐式支持 NFS/NFS4 |
| `storage_ref`、`resource_id`、`quota_domain` | 准入的逻辑引用；domain 必须对应服务器实际计费范围，不能仅凭自行命名证明独立 |
| `share`、`remote_sid` | 准确 `//server/share` 和规范数字 SID；不接受用户名查找、子路径、通配符或自由选项 |
| `archive_root`、`storage_config_digest` | 准确挂载根和固定 Ledger storage config 摘要 |
| `mount` | 恰有 `type/source/root/target/device/inode/mount_id/namespace`；type=cifs，source=share，target=archive_root |
| `tool` | 恰有 `path/sha256/version/client_config/client_config_digest/authentication_file/credential_ref/network_boundary_ref`；绝对路径规范化且互不相同，不得位于被观察 archive 内 |

`tool` 的路径和凭据逻辑引用只是私有输入引用，不含密码、token 或凭据文件内容。它们不能自证工具字节、文件所有者或网络隔离正确。写入 plan、日志或归档前仍需按私有信息规则处理路径和映射；不得从客户端接收这些字段。SHA-256 摘要绑定工具和非秘密配置；模块不计算或导出秘密文件摘要。

固定 argv 仅包含：固定可执行路径、固定 share、numeric、verbose、debuglevel=0、固定 client config／authentication file 路径、client-protection=encrypt、use-kerberos=off，以及 `--fs` 或准确 SID 的 `--quota-user`。不提供 set/list/free options。首版请求模板选择显式认证文件；这只是待准入的内部模板，不宣称现场使用此认证方式。当前没有读取该文件的执行路径。

请求环境恰有 `LC_ALL=C`、`LANG=C`，stdin 指定 DEVNULL；不继承 broker 的 USER、PASSWD、HOME、代理或密钥。未来执行器须使用完整替换环境，不能把此字典 merge 到父环境。显式 config 仍可能加载 include、外部组件或动态依赖，因此模板不能替代配置内容与完整加载面的现场审核。

`context` 恰有 `operation_id/execution_id/phase/boot_id/nas_bytes/not_before_boottime_ns/deadline_boottime_ns`。操作 UUID v4、`job-<operation>-<phase>` 和 preflight/business 必须一致；预算为正整数，观察窗口至多 30 秒且须在真实阶段预算内另行分配。这两个阶段不能重用彼此请求摘要。该 30 秒上界不是一份新作业预算，也不授权超出原 phase 截止时间。

## 3. 响应、时间和 TOCTOU 边界

每个响应含准确请求摘要、boot、开始／结束时间、exit code、完整 stdout/stderr，以及查询前后的 `binding` 与时间。binding 必须匹配全部 admission 字段，包含同一挂载 ID／namespace、share、SID、quota domain、config 和工具摘要。数字字段拒绝 bool，避免 Python 的 `True == 1` 造成伪等价。

两种查询顺序固定，前后观察时序必须完整且不交叉；任何观察不得超出 context 窗口或来自未来。相对传入的受信 `now`，两种查询最早的前置观察均不得超过一秒。跨 boot、过期、缺失、错序、响应交换、错执行／阶段、挂载或工具变化均拒绝。原始 stdout 只在调用处内存验证，返回 receipt 保存其摘要，错误消息不包含私人路径或服务器原文。

这只能检查**提供的 transcript 是否自洽**。调用者编造一致的 binding 仍可通过逻辑验证，因此返回值永远不授予业务执行权。两端观察也不能排除中间改后又恢复的 ABA，不能证明远端实际 writer SID、稳定 quota 设置、服务器身份或已生效网络限制。新鲜查询不是跨阶段的强制执行锁；真实实现还须有稳定挂载及服务端计费边界保护，失效时停止且保留 UNKNOWN／资源屏障。

首版采用保守总额条件 `0 < domain_hard_bytes <= nas_bytes`，并要求 `used <= hard`、`0 < soft <= hard`。不能只检查 `hard-used <= nas_bytes`：旧数据腾空后，一个更大的配额域仍可容纳超过单 job 预算的写入。该检查只覆盖同一计费域内同时占用的字节，不证明任意累计写入量上限。服务器计费粒度、延迟记账或允许的瞬时超额尚未实证；未来必须确保其有效最坏上限仍落在预算内。

默认限制不替代准确 SID 的限制。归档保留会逐步消耗同一域；用尽时返回失败／容量不足，不自动改 quota、换 SID、删除旧归档或重跑 NAS 作业。多个本地 profile、share 别名和其他 writer 对同一实际域的映射仍须统一资源租约；声明的 domain 名不提供分布式互斥。

## 4. 尚需冻结的私有输入与集成点

1. **实际服务端与 quota 能力：** 产品、版本、后端文件系统、准确 share／volume／quota domain；硬限制是启用还是强制执行、计费单位与瞬时超额、管理员变更约束、保留容量。不能从机型或支持 SMB 推断支持此 quota 接口。
2. **真实写入身份：** CIFS 挂载使用的远端账户／SID，以及服务端 force-user、UID 映射、multiuser、DFS/referral、别名和其他 writer。客户端 `uid=` 或 `stat().st_uid` 不是远端计费 SID 的证明。查询 SID 和 Ledger 实际创建文件的计费身份须一致。
3. **查询工具与秘密：** 准确二进制／依赖摘要与版本、保护的 config 全部加载内容、query credential 的最小权限、凭据文件身份／只读呈现／撤销与保密方式。凭据不得进入普通 Ledger helper、bootstrap 公共计划或证据 ZIP。
4. **真实监督与限定网络：** 固定 query 进程／unit 的 durable intent、身份、cgroup 与原 phase 剩余预算；只能连准确服务器的预置网络边界及实际验证。当前 `PrivateNetwork=yes` 的普通 helper 不能建立新的 SMB 查询连接，不为此整体放开其网络，也不在 broker observer 线程查询。
5. **生效与故障证据：** 服务器真实硬上限在准确 writer 身份下强制拒绝越限；正确处理查询挂起、截断、退出不明、旧回答、错服务器／SID、配额变更和挂载替换。无真实环境时继续 UNSUPPORTED，模拟不能升级为真实 NAS PASS。

未来 runner 集成须将 NAS archive 与本地 bootstrap slots 分开：本地 ext4/xfs project-quota 核验不能用于 CIFS；bootstrap/preflight 的 archive 只读，业务执行才可在全部门槛通过后获得准确 archive 写权。当前 `_admit` 最后只保留 allocation.paths，因此只删除 UNSUPPORTED 既不完成配额验证，也不正确开放 NAS 写入。

查询需处于已有监督、预算、取消和启动围栏之内，结果由隔离读取边界收集；缺少完整退出证明时保留 UNKNOWN、租约与容量屏障，不复用旧响应或自动启动另一查询。`validate_responses` 的调用者、时钟和 binding 采集未来必须来自受信内部实现，不能把本模块当作客户端自报事实 API。

固定 Ledger `6bd6acfbe5c35d581891eb87275e1173e17848fc` 的 NAS 程序仍使用原四参数；不新增 run-id/resume，不修改上游脚本，不删除 NAS 归档。真实服务器或工具事实若推翻已批准的隔离、预算或固定调用语义，按既有变更规则处理；此说明没有新建 Gate 或重开已授权 E1–E3。

## 5. 当前验证范围

专属测试通过内存 mock 的固定两种工具响应覆盖格式、特殊值、硬上限、错 SID、退出码为零的不支持响应、配额未强制执行、身份变化、错误时间、请求重放、输出边界和无条件 live 拒绝。所有输入为合成值；没有安装 Samba、启动真实查询进程、读取真实凭据或连接 NAS。

定向命令：`python -m unittest discover -s tests -p test_local_hand_jobs_nas_quota.py -v`。准确候选和本轮结果由主验证报告记录。该测试不完成 E3 的真实 cgroup／文件系统验证，也不完成 E5/E6 私有部署和 NAS 验收。
