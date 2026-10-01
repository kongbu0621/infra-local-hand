# Q2 系统管理器启动修复：实现审核

本实现属于 Owner 已批准的 `LH-Q2-SYSTEM-MANAGER-REPAIR-v1` M1–M4。
准确 A 为 `ae50aea2639c32021794ecb70730f4b9e781c8d6`，独立 CLOSED C 为
`23702d6e55396d7941389817ab875a4610d3e142`。A 的三份文档原字节保持不变。

## 实现与原故障的对应关系

原故障发生在 user manager 为普通 worker 建立隔离、下降 capabilities 的阶段，
早于 Python 入口。新版本由现有 root controller 内的固定 gateway 请求 PID 1
建立同样的普通 worker 隔离；普通身份、零 capabilities、NoNewPrivileges、
namespace、路径隔离和全部资源限制仍须通过原检查。

`SystemManager` 接入原 Runner 的阶段交付边界，共用原阶段、结果读取、取消与
quota lifecycle。独立 root 模块不是任意命令入口，也未扩展只读 quota observer。
普通消息只含阶段引用及 grant/allocation 摘要，root 从受保护配置与原 journal
重建命令。新的 policy、manager binding、resident、launcher、装配、监督、
handoff 和证据 schema 均显式选择 system 语义；旧 user 版本不自动迁移。

每阶段首次交付前持久化意图。对端 PID/start time、凭据、boot、父级 inode、
InvocationID、原管理 client、真实双流 EOF 与 stop ACK 共同约束后继阶段。
响应丢失、peer 断开、未识别 unit、前驱未关闭或隔离属性改变均停止推进。
仅关闭协议或一个 client 不产生成功退出证明。失败意图和资源义务保留。

新普通子 slice 位于不变的 controller-parent 内，与 target 为兄弟；
target 和普通子 slice 各为 256 MiB/32 tasks，共受父级 512 MiB/64 tasks 约束。
旧普通父级独立保留。supervisor 仍检查整个 controller-parent 是否关闭。
bootstrap/helper/reader 的原 3/4/3 CPU-s 与绝对期限保持不变。

## 有界性与审核中修复的问题

单操作最多九次 stage 首次交付、256 次协议请求和 256 次 root 管理命令。
协议流量与实际管理输出（包括失败时已读取字节）共同受 4 MiB 上限约束；
意图和至多 32 KiB 诊断使用原 target 1 MiB/64 文件池。`gateway.json`
只保存安全身份、计数、有限故障代码和原实例状态，不保存原始请求或环境。

system backend 的观察间隔为 0.5 s，旧 user backend 仍为 0.05 s。
原取消事件可以立即唤醒等待，未刷新任何期限。完整健康链的保守上界为
195 次协议调用、205 次 root 管理命令；额度不足仍停止，不扩容。

联合审核修复了以下实际问题：CPU 百分比的整数/一位小数换算；reader payload
错误绑定 helper unit；root 上下文误构造普通账号的 runtime 路径；gateway
内部故障没有传播到 launcher；失败管理输出漏记；原 50 ms 轮询过早耗尽
调用额度。实际 unit 的路径列表、SendSIGKILL 与其他隔离属性均重新核验。

## 验证结果与边界

67 个定向测试模块共执行 **985 项：962 项通过、23 项明确跳过、0 失败、0 错误**。
[机器可读结果](validation/q2-system-manager-20261001/targeted-tests.json)
列出所有模块与跳过原因。覆盖旧版本兼容、实际管道/FD、合成阶段闭环、
错误身份、重放、断开、截断、剩余预算、父树残留、版本混配及证据封存。
Windows 收集路径保留平台条件，不在导入阶段无条件加载 Linux IPC 模块。
CI 的变更过滤器已包含新的独立管理模块目录。

当前执行环境的 procfs 与 PID namespace 不一致，并对部分 AF_UNIX 操作及
普通身份映射有限制。相关真实检查明确跳过；测试替身的通过不替代这些检查，
也不代表原 guest 的 systemd/AppArmor 路径已通过。未在云端启动原 guest 正常链。

## 单次交付和后续验收

从准确、干净的实现 commit 构建 source bundle 与带内置 provenance 的 wheel。
私有交付采用显式 code-update v2，核对原安装回执与新 source/payload，复用旧
Python 和普通账号；原同 payload v1 入口保持不变。原生产 wrapper 保持禁用。

私有包由原本地执行端复用 SSH，先独占消费标记，再在同一 300 s 原点内完成
有限准备和最多一次原正常链。首次普通可写对象创建前须完成全部旧生产者准入；
旧 UNKNOWN、lease、unit、安装和费用保持原状。不存在、部分完成或超时的证据
不能被填成成功。不得重装、清场、重启旧 manager、重试或修改全局 AppArmor。

此处记录实现和离线验证；M4 原 guest 执行与验收尚待准确私有包的真实返回。
`q2_accepted=false`、`q3_accepted=false`、`production_supported=false` 仍然成立。
