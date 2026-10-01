# Q2 系统管理器启动修复：需求

- Authority：Owner；状态：PROPOSED / Gate OPEN。
- Scope：`LH-Q2-SYSTEM-MANAGER-REPAIR-v1`，实施阶段 M1–M4。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，采用与完整性规则继承根 `AGENTS.md`。
- 输入源码：`7780364c23497e989cd320f157cb4f512a798028`。
- [原因证据](../Q2_APPARMOR_FAILURE_REVIEW.md) → [架构](ARCHITECTURE.md) → [实施](IMPLEMENTATION_PLAN.md)。

## 用户目标与范围

用户需要 Local Hand 实际完成已有 `host.inspect` 正常链，而非重复安装、
反复收集日志或移除安全检查。当前业务入口在 Ubuntu 的 user-manager
隔离准备阶段失败；新的空账本又遇到旧 manager 中保留的未知执行。

R1：仅在既有隔离 Q1 guest 中实现固定系统管理器适配器，走同一
Broker/Runner 和 `preflight → business → evidence` 链。
复用既有 SSH、普通身份、Python 安装、文件系统和只读 quota observer。
在新受保护代码目录交付准确候选，不覆盖旧安装。

R2：隔离由系统级 systemd 建立；broker 和全部 bootstrap/helper/reader
仍用原普通 UID/GID。业务入口必须具有五组零 capabilities、NNP=1、
独立 user/network/mount namespace，并满足原设备、路径、配额及资源限制。
普通 broker 不取得 root、sudo、polkit 授权或通用系统管理接口。

R3：新增管理入口只服务本次固定操作、三个 phase 及各自三个 stage。
禁止任意命令、路径、unit、属性、环境变量和重复交付；无通用 shell。
管理入口是新增受信责任，不冒称既有 quota observer 已有此权限。

R4：原 boot、operation/execution、allocation、grant、绝对期限、unit、
InvocationID、cgroup 和原管道证据继续绑定。未知交付、过期、身份变化、
输出截断、退出不明均停止后续阶段并保留 UNKNOWN 及相关资源。

R5：旧 user manager、所有旧 unit、数据库、lease、配额和日志保持原状。
新任务使用系统级普通任务子 slice、新账本与七个新项目根。该子 slice 与
target service 为兄弟，共用原 controller 父级上限；历史容量完整继续计费。
新父级隔离不能证明旧执行关闭，也不允许再用旧资源。

R6：交付一个含 `TASK.txt` 的单次 ZIP。一个独占消费标记先于任何现场修改；
标记已有、部分写入或先前执行不明均拒绝。整包只允许一次正常链，
不自动重试、不重装、不重启旧 manager、不清理现场。

## 精确变更与保留边界

仅在本 scope 获准后，替换 fixture preparation P02/架构中“普通三阶段
必须在 user@ 委派子树启动”的要求，改为固定系统 manager 与新普通任务父级。
原普通 broker 的身份要求不变；worker identity、quota、取消与 UNKNOWN
合同不变。quota observer 的只读接口保持原样，另增受限启动责任。

不改变既有 Task v1/六类作业需求；不恢复退休 native spike；不升级系统包、
内核或 AppArmor 配置；不开放生产 backend、不进行 GX10/NAS/E4–E6 部署。
旧版本 policy、handle 和测试事实不能自动迁移到系统 manager。

## 验收与失败信号

M1–M3 的离线成功只证明实现合同与包完整性。M4 必须保留唯一原执行，证明：

1. PID 1 启动的各阶段确实进入 Python，普通身份、五组零 capabilities、
   NNP 和实际 namespace/路径/配额检查全通过，隔离警告不能当作成功。
2. 原固定 `host.inspect` 操作完成 preflight、business、evidence，结果和
   原 client/管道/退出、停止及父树证据通过已有验收器。
3. 所有新控制生产者及系统管理请求都被计费与监督；旧 UNKNOWN、lease 和
   已消费额度保持原结论。没有第二次启动、清理或隐含重试。

任何一项不满足则保留首错并结束。`q2_accepted` 只由完整原验收证据决定；
`q3_accepted` 和 `production_supported` 不随此正常链自动变真。
待 Owner 决定的是上述准确启动边界与 M1–M4 的单次范围；不请求降低校验。
