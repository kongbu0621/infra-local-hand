# Q2 协议与客户端：第一批实现验证

2026-09-25。**严格协议与有界客户端已实现；31 项逻辑测试通过，11 项真实 IPC 测试
因执行器权限跳过。Q2 整体未完成，生产 E3_SUPERVISION_UNVERIFIED 保留。**

本批源码 `3aa851fa102b7861f8a301e3c07236d6b3864858`，tree
`e7f83d1ef00380758cd26a4c84cf266d6d95274d`，继承已批准 A/C。
编码合同先在 `ac8ae70` 固定，见 [wire 合同](E3_QUOTA_Q2_WIRE_CONTRACT.md)。
前置 Q1 结论仅限 [原隔离 guest 的已交付容量范围](E3_QUOTA_Q1_GUEST_CAPACITY_REVIEW.md)。
本文不变更批准的三份权威文档或旧失败结论。

## 本批实现

| 位置 | 行为 |
| --- | --- |
| tools/local_hand_jobs/quota_contract.py | 8 KiB 请求/32 KiB 回执、严格 JSON/类型/版本/字段；保留完整执行 ID 与 phase；全部请求字段进入摘要和确定 query unit |
| 同一合同的根事实检查 | 核对 work/evidence/temporary；evidence 阶段允许受信配置中的 retained_store；完整身份、FS UUID/project、额度、继承和 enforcement 逐根匹配；拒绝 inode/FS 别名与同域额度冲突，按域去重且检查总和溢出 |
| 同一合同的结果检查 | 每根固定三次 syscall 的有序原 rc/errno，首次失败后不得继续；准确 query identity、退出/采集/双 EOF、原 deadline 及收紧后的 receipt deadline；返回不可变规范字节，不产生启动/释放资格 |
| tools/local_hand_jobs/quota_client.py | 一连接一次交付；4 字节长度帧、请求 half-close、响应必须 EOF；保护 endpoint 元数据和 SO_PEERCRED 校验；接收 FD 全部关闭后拒绝；BOOTTIME 原 deadline 覆盖 connect/send/recv/EOF/消费，无自动重发 |

客户端没有 admin 导入、提权、quota 调用、派生进程/线程、业务启动或账本修改。
声明校验与受认证服务报告不等于独立 OS 证明。调用者须提供受保护的安装、原请求与根绑定；
文件系统检查只能置于原监督 bootstrap，不能在 broker 控制线程调用。
socket 拒绝 other 权限和特殊权限位；祖先必须由管理员拥有且普通身份不可写。
Linux 使用 poll，避免继承高编号 FD 时落入 select 的 FD_SETSIZE 限制。

## 准确验证结果

命令：`python3 -m unittest discover -s tests -p 'test_local_hand_jobs_quota_*.py' -v`。
Python 3.12.14，Linux 6.18.44，退出码 0：42 项中 **31 通过 / 11 SKIP / 0 失败**。
准确命令、时间、源码和测试摘要见
[targeted-command.json](validation/q2-wire-client-20260925/targeted-command.json)，
完整输出见 [targeted.log](validation/q2-wire-client-20260925/targeted.log)。
日志 SHA-256：`e6c1469af16d6703038edecdb1b177bcbc338fcf0a7d3fcfd0b325079aa39a72`。

通过项覆盖字节/深度边界、重复/未知键、非法 Unicode、布尔伪整数与 64 位时限、所有绑定字段
变异、多根及第四根、共享域去重和矛盾、全部退出字段、错误 peer/endpoint 声明、原时限、
半包/多余字节、缺 EOF、发送阻塞、连接排队失败、响应期限收紧、FD 关闭和异常消毒。
传输通过项使用显式脚本化 socket，属于 LOGIC_ONLY；FD 关闭用真实匿名 pipe/dup 描述符，
不声称已执行内核 SCM_RIGHTS 传递或实际 SO_PEERCRED 认证。

首次尝试 28 项时，17 通过、11 error；全部 error 发生于 AF_UNIX socket 创建，errno=1。
随后请求受控提权运行同一测试，工具自动审批策略明确拒绝，原因为 sandbox_approval=false。
环境受限经过和未验证项见 [首次受限记录](validation/q2-wire-client-20260925/environment-block.md)。
未改用其他入口绕过此限制；真实 IPC 测试保留，权限拒绝明确记录为 SKIP，不记 PASS。
没有在用户 VM 上运行新命令，没有 quota/systemd 实测，也未重跑完整产品安装矩阵。

## 下一批与恢复位置

下一批组合服务端持久防重、原管理预算准入、多根查询装配与 bootstrap 事实消费。先补齐这些
源码和恢复负例，再给用户一份固定版本的集成操作，避免逐项重复查询旧 fixture。

仍未完成：受信配置/授权原件与 socket 双向身份、bootstrap/helper/reader 入口隔离、服务端
有限请求账本与 UNKNOWN 保留、原预算/跨阶段绑定、真实 query/collector 退出、bootstrap
本地 FD 最终复查、实际 IPC、Q3 三单元正常链及 Q4 故障恢复。现有 broker/runner/bootstrap
没有接通本客户端，不能将本批解析出的 OBSERVED 当作生产准入。

旧 slot-001 UNKNOWN、slot-002 INCOMPLETE、原 reservation 和证据保持原样；新 Q2 不借用
这些已消费对象。无需重跑 Q1、重格式化磁盘、扩大额度或清理旧现场。
