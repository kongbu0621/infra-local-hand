# Q2 管理进程超时修复与失败日志

**2026-10-01 后续更正：**完整内核与原 bootstrap 日志现已证明，普通执行器
因 AppArmor 拒绝降 capability 而先退出，约 1.076 秒后 listener 才超时。
下文保留当时的观察和修改记录，但“等待预算不足是首要原因”的判断已被
[完整原因复核](Q2_APPARMOR_FAILURE_REVIEW.md)取代。8/7/5 秒配置没有解决
这个启动原因；下一批在旧 manager 库存检查处已停止，尚未现场验证该配置。

2026-10-01 的原现场已经通过 `b37935d` 的 session 格式修复，随后以
`MANAGEMENT_CLIENT_FAILED` 结束。本记录属于既有 CLOSED E1–E3/Q2 合同内的
定向装配与诊断修复，不改变授权范围、验收条件或失败现场。

## 已证实的故障

原 listener 的 systemd 状态与原 boot、unit、InvocationID 一致。
PID 1 的同次 invocation 日志明确记录运行时间上限到达，最终
`Result=timeout`、`ExecMainCode=2`、`ExecMainStatus=15`。
admission 在 listener 退出约 12.259 ms 后退出 2，自身未到 2 秒上限。
两者内存峰值约 30 MB，限制为 64 MiB；本次没有 OOM 结果。

原配置给 collector 和 admission 各 3 秒。`q2_runtime.command` 按既有合同
从各自上限中预留 1 秒停止时间，因此实际运行上限只有 2 秒。
listener 还要等待 admission 就绪、普通执行器启动、请求到达及查询返回；
这个配置已在原现场造成提前终止。

admission 是否因 listener 关闭控制连接而退出，尚不能从现有证据精确证明：
其 Python stderr 原来只在 controller 内存中，没有保存。
resident 随后因控制端退出收到 EOF，报 `BRIDGE_CREDENTIALS`；外层
`HANDOFF_ORIGINAL_CAPTURE_INCOMPLETE` 仍是包装结果。

只读补采中，绑定原 boot 与 InvocationID 的查询各取得 5 条完整日志；
额外时间窗查询因 `--boot` 的带连字符 UUID 格式被该 guest 拒绝，故整包为
`PARTIAL`。这里仅采用成功、完整且精确绑定的查询及原 unit 状态，不把整个
补采包改记为 PASS。原证据保持私有。

## 针对性修改

重新分配下一单次运行的受保护 stage 配置，不修改 runtime 的限时算法：

| 角色 | 原 stage 上限 | 新 stage 上限 | 新实际运行上限（预留停止时间后） |
|---|---:|---:|---:|
| collector/listener | 3 s | 8 s | 7 s |
| admission | 3 s | 7 s | 6 s |
| query | 6 s | 5 s | 4 s |

三个 stage 加接收 1 秒、停止 1 秒，共 22 秒；原操作仍为 72 秒、每阶段
24 秒、原普通执行器停止宽限仍为 1 秒。原 `decode_grant` 对实际 issued 时间
与剩余 phase deadline 的校验保持原样；准备过晚仍必须拒绝，不能刷新旧期限。

每个管理 stage 的 CPU 仍为 2 秒、内存仍为 64 MiB、任务数仍为 8，输出、存储、
父级资源与身份校验均保持不变。原公式据新 stage 上限分别计算 22%、25%、33%
的 CPUQuota；没有通过单独增加 RuntimeMaxSec 绕过 CPU 总量约束。

失败日志同时补齐两处：管理客户端原检查失败时，把已经取得的 role、退出码、
Capture.error、EOF、双流长度/摘要及原 invocation/terminal 信息写入既有外层
stderr；`q2_entry` 保留退出 2 和 `Q2_ENTRY_REJECTED`，附加有界的错误代码、类型、
errno 与源码位置。不打印局部变量、凭据、请求内容或任意异常文本。
日志写入失败不改变原错误，也不增加 manager 查询或重试。

## 验证与交付边界

回归检查原 grant 解码、实际 fixed argv、CPU 上限、过期/超限拒绝及诊断的
脱敏、输出边界和原异常保留。定向源码检查共 104 项：102 通过、2 项环境跳过
（AF_UNIX 不可用、普通 UID 65534 未映射），没有把跳过记为通过；其中新增诊断
14 项和时间窗口 7 项全部通过。新运行包复用原 Python、native 工具和 SSH，
只在新代码目录放置与新 commit 一致的源码及真实 wheel 元数据。
保留四个历史正常链批次的完整额度与证据，包括上一代码更新的独立额度。

新参数增加已证实不足的等待时间，并不证明现场功能已经通过；查询启动过晚或
后续其他原检查失败仍会停止。新正常链只执行一次，不自动重试、不清理现场。
`q2_accepted`、`q3_accepted`、`production_supported` 在取得完整原验收证据前
仍为 false。
