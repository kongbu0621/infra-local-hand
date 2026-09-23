# NAS 私有输入工作表

日期：2026-09-23。用途：收集真实 NAS 配额查询与后续隔离验收所需的现场事实；本表不是运行配置、准入决定或部署命令，不修改已批准的三份 A 基线文档。

**真实 NAS collector 尚未实现。** 当前仅有 `smbcquotas-user-v1` 固定请求构造和响应逻辑验证；成功结果仍为 `LOGIC_ONLY`、`business_authorized=false`，`execute_live_queries()` 始终 `UNSUPPORTED`。填写本表、声明支持配额或提供成功响应，均不能通过配置开关启用真实查询或 NAS 写入。E3、E4、E5/S2、E6 各自的现场证据与授权范围仍须区分，S2 保持 OPEN。

本仓库只保存这份空白模板。请在私有副本填写准确值和证据引用；不要把填写后的服务器地址、共享名、绝对路径、账户或 SID 提交到公开仓库。**任何副本都不填写密码、token、私钥、票据或凭据文件正文，也不计算、附带或公开秘密文件摘要。** 秘密只记录逻辑引用、提供方式及权限要求；二进制和非秘密配置可记录摘要。所有未知项写 `UNVERIFIED`，没有依据的“不适用”也保持未验证。

依据：[NAS 配额合同与剩余准入](NAS_QUOTA_ADMISSION.md)、[S2 现场准备状态](../s2/READINESS.md)、[实施状态](IMPLEMENTATION_STATUS.md)。本表字段比当前模块声明结构更广，用于现场核对；不得直接复制到 Policy/profile，未知字段不会自动获得实现支持。

## 1. 目标与可用入口

| 私有输入 | 待填写值 | 所需依据 |
| --- | --- | --- |
| 记录版本、填表时间、信息提供方逻辑引用 | `<WORKSHEET_REVISION>` / `<UTC_TIME>` / `<CONTACT_REF>` | 每次修改保留版本和来源 |
| 目标执行主机、用途 | `<HOST_REF>` / `<ISOLATED_E3_OR_LATER_SCOPE>` | 明确是隔离 E3 验证主机还是另行批准的部署目标；机型不证明权限 |
| 该主机 OS、架构、内核、systemd 版本 | `<HOST_FACTS_REF>` | 准确主机近期只读观察；不能用开发容器或历史报告代替 |
| 当前已提供的执行入口 | `<BOUND_EXECUTION_ENTRY_REF>` 或 `UNVERIFIED` | 入口必须绑定准确目标、调用者、准入动作和当前可用性；仓库 Connector 不等于主机 shell |
| 入口权限与允许动作 | `<READ_ONLY_OR_EXECUTION_SCOPE_REF>` | 列出允许读取/执行的范围；旧 mailbox 八动作不能推导任意 shell、systemctl 或扩大 allowlist |
| 隔离运行身份与预置监督条件 | `<ACCOUNT_REF>` / `<DELEGATION_REF>` / `<LOCAL_HARD_QUOTA_REF>` | 专用非 root 身份、既有委派 cgroup、namespace 与本地硬配额；实际路径和账户只放私有记录 |
| 准确源码、wheel 和现场任务范围 | `<SOURCE_COMMIT>` / `<WHEEL_DIGEST>` / `<SCOPE_DECISION_REF>` | 不自动升级候选，不把 E3 通过写成 S2 切换或 E6 NAS 业务通过 |

历史 GX10 S1 或旧 mailbox 回执只能证明记录时的限定动作。没有当前入口绑定及观察时，不能据此声明主机在线、可执行 E3、已安装新 broker，或反向断言主机离线。

## 2. 实际协议、服务端与硬配额域

| 私有输入 | 待填写值 | 必须分清的事实 |
| --- | --- | --- |
| 实际协议与协商版本 | `<SMB_OR_NFS_AND_VERSION>` | 当前逻辑合同仅覆盖 SMB/CIFS；NFS/NFS4 没有可套用的 SID 查询适配器 |
| 服务端产品、准确版本、后端文件系统 | `<SERVER_PRODUCT_VERSION>` / `<BACKEND_FILESYSTEM>` | 支持 SMB 不等于支持用户 quota 查询与强制硬限额 |
| 服务器身份与端点映射 | `<SERVER_IDENTITY_AND_ENDPOINTS_REF>` | 准确服务端身份、别名、集群/故障转移、DFS/referral 情况；地址仅存私有映射 |
| 共享或 export、volume/dataset | `<SHARE_OR_EXPORT_REF>` / `<VOLUME_REF>` | 私有副本记录准确对象，禁止通配符或把子路径当独立配额域 |
| 实际计费域及配额机制 | `<QUOTA_DOMAIN_REF>` / `<USER_GROUP_PROJECT_DATASET_OR_OTHER>` | 域名只是逻辑标签，须有服务端机制证明实际边界 |
| 配额启用与强制执行状态 | `<ENABLED_AND_ENFORCED_EVIDENCE_REF>` | “已启用”、soft limit、容量提示或查询 exit 0 不能代替 hard enforcement |
| 域内已用量、soft、**总 hard 上限** | `<USED_BYTES>` / `<SOFT_BYTES>` / `<HARD_BYTES>` | 使用准确字节单位；不能以 `hard-used` 或 share 空闲空间代替总 hard 上限 |
| 计费粒度、延迟、瞬时超额及最坏边界 | `<ACCOUNTING_BOUND_REF>` | 明确实际计费对象和最大有效占用；未验证时不把名义 hard 值当严格上限 |
| 其他 writer、既有数据与归档保留 | `<OTHER_WRITERS_AND_RETENTION_REF>` | 同一域的历史归档持续占容量；不足时不能自动删档、换身份或提升配额 |
| 配额/身份/服务端映射的变更约束 | `<CHANGE_CONTROL_AND_STABILITY_REF>` | 一次新鲜查询不阻止查询后改变配额；前后相同也不能排除中间改变后恢复 |

现有 SMB 逻辑合同要求 `0 < domain_hard_bytes <= job_nas_bytes`、`used <= hard`、`0 < soft <= hard`，且拒绝零值、无限/无条目语义及不支持响应。它只检查同一域的同时占用，不证明累计写入量上限。若现场机制不同，先记录差异并评估所需实现；不能改填数字使其表面符合。

## 3. 实际 writer 与查询身份

| 私有输入 | 待填写值 | 所需证明 |
| --- | --- | --- |
| Ledger 实际写入进程的身份 | `<LOCAL_WRITER_IDENTITY_REF>` | 运行账户、namespace、挂载使用者的准确绑定 |
| SMB 远端 writer 数字 SID | `<REMOTE_WRITER_SID_REF>` | 服务端对实际新文件计费的 SID，须与 quota 查询 SID 一致；公开副本只保留引用 |
| 身份转换链 | `<IDENTITY_MAPPING_EVIDENCE_REF>` | 客户端凭据到服务端账户/SID，以及 force-user、UID 映射、multiuser、别名等实际规则 |
| 查询身份与最小权限 | `<QUERY_IDENTITY_REF>` / `<QUERY_PERMISSION_REF>` | 查询身份可以不同于 writer，但必须能读取准确 writer 的 quota；不授予设限、删除或管理写入权 |
| NFS 身份模型（若适用） | `<NFS_IDMAP_SECURITY_AND_SQUASH_REF>` | UID/GID、idmap、security flavor、root/user squash、export 与计费域；现有 SMB 适配不支持此分支 |
| 同域资源互斥映射 | `<RESOURCE_ID_AND_ALIAS_MAP_REF>` | 多 profile、多 share/export 别名、其他 writer 是否共用实际计费域；声明逻辑 ID 不证明分布式互斥 |

客户端 `uid=`、本地 `stat().st_uid` 或仅有账户名都不是远端计费身份的充分证据。尚无准确 writer 映射时保持未准入，不根据机型、默认用户名或已有读权限推断。

## 4. 固定查询工具、配置与秘密引用

| 私有输入 | 待填写值 | 边界 |
| --- | --- | --- |
| 查询工具路径逻辑引用、版本、来源与 SHA-256 | `<TOOL_PATH_REF>` / `<TOOL_VERSION>` / `<TOOL_SOURCE_REF>` / `<TOOL_SHA256>` | 当前解析基线 Samba 4.23.0 不是已获准运行的二进制；须绑定实际工具及动态依赖 |
| 工具依赖与完整配置加载面 | `<DEPENDENCIES_REF>` / `<CLIENT_CONFIG_REF>` / `<NONSECRET_CONFIG_DIGEST>` | 包括 include、插件和外部组件；显式指定 config 不自动排除额外加载 |
| 工具、配置的属主、权限与只读呈现 | `<FILE_IDENTITY_AND_PERMISSIONS_REF>` | 不能位于被观察 archive 内；路径、文件身份与摘要在执行前后保持绑定 |
| 凭据逻辑引用 | `<CREDENTIAL_REF>` | 只给秘密保管系统或本机管理记录中的逻辑名称，不填秘密值或秘密摘要 |
| 凭据提供方式与撤销/过期规则 | `<CREDENTIAL_DELIVERY_REF>` / `<REVOCATION_REF>` | 只读提供给未来专用查询进程；不得进入普通 Ledger helper、公开 bootstrap plan 或证据包 |
| 认证模式与当前模板是否相容 | `<AUTHENTICATION_MODE_AND_GAP_REF>` | 当前固定请求使用显式认证文件、要求加密、关闭 Kerberos；现场不相容时记录缺口，不能追加自由 argv |

现有请求模板仅构造两个固定只读查询（filesystem、准确 SID 的 user quota），没有 set/list/free options；环境限定为 `LC_ALL=C`、`LANG=C`，stdin 为 DEVNULL。未来 collector 必须替换整个环境，不继承 broker 的凭据、代理或密钥。凭据身份/权限检查尚须由真实实现完成，本表不执行任何凭据读取。

## 5. 挂载、限定网络与监督预算

| 私有输入 | 待填写值 | 所需约束 |
| --- | --- | --- |
| 准确 archive root 与 Ledger storage config | `<ARCHIVE_ROOT_REF>` / `<STORAGE_CONFIG_REF>` / `<NONSECRET_CONFIG_DIGEST>` | 私有记录保存真实映射；不从客户端 job 参数接受任意路径 |
| 挂载观测绑定 | `<MOUNT_TYPE_SOURCE_ROOT_TARGET_DEVICE_INODE_ID_NAMESPACE_REF>` | 需证明真实协议、同一挂载和服务器映射；本地 ext4/xfs project quota 不能充当 CIFS/NFS 配额证明 |
| 预置网络边界逻辑引用 | `<NETWORK_BOUNDARY_REF>` | 绑定将来的固定查询进程，不能整体放开普通 helper 网络 |
| 允许的服务端身份、端点与端口集合 | `<APPROVED_ENDPOINT_AND_PORT_SET_REF>` | 私有映射应明确 DNS/认证/DFS/故障转移是否需要额外目的地；未准入目的地应拒绝 |
| 实际网络限制的生效与负向证据 | `<NETWORK_ENFORCEMENT_EVIDENCE_REF>` | 配置声明不等于生效；不得用本表执行连通性探测 |
| query unit、取消与退出观察的实现绑定 | `<QUERY_SUPERVISOR_DESIGN_REF>` | 尚待实现；具有 durable intent、准确身份、递归树退出和停止宽限，不能在 broker observer 线程查询 |
| 原 operation/phase 预算与查询窗口 | `<PHASE_BUDGET_AND_QUERY_WINDOW_REF>` | 查询消耗原剩余预算，不新授预算、不跨阶段复用响应；现有逻辑窗口上限不代表额外时间授权 |
| 缺失/超时/挂起响应的保留策略 | `<FAILURE_AND_RETENTION_REF>` | 保持 UNKNOWN、租约和容量屏障；不能将截断、无回执或旧响应当作通过并自动重试 |

普通 helper 当前使用 `PrivateNetwork=yes`，不能据此建立新的 SMB 查询连接。真实 collector 的限定网络、秘密隔离、监督和调用链仍须实现并验证；只删除 NAS 拒绝分支不能补齐这些能力。

## 6. 现场证据与下一步交付

每个证据引用在私有副本记录：准确对象、采集时间、采集主体/入口、只读或隔离测试范围、完整性摘要、已确认事实及仍未知部分。秘密不进入原始日志或 ZIP；不能脱敏的现场映射留在受控私有清单中。

| 待交付证据 | 私有引用与状态 |
| --- | --- |
| 服务端实际协议、产品版本和配额强制执行机制 | `<SERVER_FACTS_REF>` / `UNVERIFIED` |
| 真实 writer 到服务端计费域的绑定 | `<WRITER_QUOTA_BINDING_REF>` / `UNVERIFIED` |
| 固定工具、非秘密配置和最小查询权限 | `<QUERY_INPUTS_REF>` / `UNVERIFIED` |
| 预置限定网络、挂载稳定性及变更约束 | `<ISOLATION_FACTS_REF>` / `UNVERIFIED` |
| 原预算内查询监督、取消、阻塞 I/O 与重启恢复的验收范围 | `<E3_CHECKS_AND_SCOPE_REF>` / `UNVERIFIED` |
| 准确 writer 的硬上限拒绝、旧响应/错身份/挂载变化等隔离验证范围 | `<NAS_ACCEPTANCE_SCOPE_REF>` / `UNVERIFIED` |
| 私有证据归档位置与对外脱敏规则 | `<PRIVATE_EVIDENCE_REF>` / `UNVERIFIED` |

首次回复可以只提供：实际 SMB/NFS、服务端产品与版本、已知 quota 类型、拟用执行主机逻辑引用、当前可调用入口及其动作范围、负责提供余下事实的逻辑引用。其他项保留 `UNVERIFIED`，不要求粘贴秘密或先执行现场变更。

资料齐备后的结果是可审查的私有输入清单与明确实现缺口。真实 collector 接入、隔离 E3 验收、实际客户端连接、S2 切换与 E6 NAS 业务验收仍分别按既有范围推进；本表本身不完成任何一项。
