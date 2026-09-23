# E3 配额机制与真实 harness：变更需求

- Authority：Owner；日期：2026-09-23；状态：PROPOSED / Gate OPEN。
- scope：`LH-E3-QUOTA-HARNESS-v1`。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，直接来源及采用关系见根 AGENTS。
- 本组三份文档是该变更的权威文档；准确 A 为包含它们的文档提交，由后续登记记录。
- 继承原 A `79f73faedcd9cde4164b0d1625782dae27db6c2f` 的 AX-R01–R12；
  原文保留。本变更只扩展配额事实取得和实机验收装配，不重开 Ledger A2、S1 或无关已批准工作。

## 要解决的问题

当前实现要求普通、隔离的 bootstrap 自己查询 project hard quota。固定上游源码显示查询需要
host 权限，而作业使用 PrivateUsers/PrivateDevices；部署侧预设 quota 不能解决查询权限。
真实三单元测试仍是占位。GX10 一次性输入确认也未找到可准入的专用 E3 环境。
事实依据见 [实现缺口](../E3_IMPLEMENTATION_GAPS.md)和[输入核验](../GX10_E3_INPUT_CONFIRMATION_VERIFICATION.md)。

目标是让固定受限作业取得可核验、准确绑定的配额事实，并用真实 systemd 三单元链证明
预算、取消、恢复和结果读取；随后才有可能形成 E3 合格候选。配置写了数值、CI 通过或完成盘点均不够。

## 本次建议批准的范围

开发一个单独受信、仅查询已准入本地 project quota 的管理侧组件，及其受限客户端和
真实 test-only harness；在已有、明确交付的隔离 fixture 上验证。组件不进入普通作业的权限域。
先完成最小可行性检查；失败即保留证据并暂停依赖它的工作，不为继续验收放宽条件。

本次不批准对 GX10 创建账户、安装特权服务、委派资源、挂载或设置 quota；
这些动作需在代码与装配方案就绪后，按准确私有对象和影响另行交付给既有管理入口执行。
不改变 E4、E5/S2、E6 的边界，不接真实 NAS，不新增远程管理或任意执行能力。

| ID | 必须达到的行为 | 失败判据 |
| --- | --- | --- |
| QH-R01 | bootstrap/helper/reader 继续专用非 root、原 namespace 隔离；只有独立管理侧查询器拥有查询所需 host capability | 普通作业获得 host 管理权限或关闭原隔离 |
| QH-R02 | 查询只针对管理侧预先固定的有限 roots/projects；客户端只给逻辑 ID 和原执行绑定 | 接收任意路径、device、project ID、argv、代码或 quota 设置命令 |
| QH-R03 | 事实绑定当前 boot、部署代次、slot generation、执行/预算、准确文件系统与目录身份；原始返回值和即时 errno 留存 | 只信布尔值、配置文本、过期缓存或可替换路径；跨作业复用旧成功 |
| QH-R04 | kernel hard quota 实际强制；合并计费域和封存峰值不超过原预留；不能修改继承身份或转写未计费域 | 只查到 hard limit 却未证明 enforcement；通过放大预算取得通过 |
| QH-R05 | 管理侧查询本身受独立监督和有限容量约束；阻塞不占 broker 控制线程；未知不释放或反复派生 | 把查询当零副作用、超时当退出或失联后自动补投 |
| QH-R06 | test-only harness 执行同一真实生产监督核心、持久意图及启动围栏；逐场景原始证据 | mock quota/manager、写死资格、改变断言或把 sleep 当内核 I/O 阻塞 |
| QH-R07 | 原失败、errno、停止不明、各 unit 和 collector 的事实分别封存 | SKIP/BLOCKED/UNKNOWN 当作 E3 PASS；重试覆盖旧证据 |

## 完成定义与待决事项

完成需有准确源码/安装/管理侧产物身份、可信通信与负例、真实超限写入拒绝、
H01–H13 所适用的完整实测和独立证据核验，未覆盖项保留阻塞。只实现查询器不算解决 E3。
生产 `E3_SUPERVISION_UNVERIFIED` 在本次开发和测试阶段保持；移除需随后依据完整实测单独审阅。

Owner 此次需要决定的是：是否接受这个新增管理侧受信组件，并批准上述隔离开发范围。
其 host capability 权限较大；“仅查询”是需实现并验证的应用限制，不是 Linux 提供的细粒度 capability。
无法在准确 fixture 内落实权限、固定对象和停止边界时，对应实测 BLOCKED，不自动借用桌面或 S1 账户。
