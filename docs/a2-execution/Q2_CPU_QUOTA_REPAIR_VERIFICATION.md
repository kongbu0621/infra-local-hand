# Q2 恢复后启动失败：CPU 配额修复与证据

2026-09-27。状态：**现场根因已确认，源码修复及离线回归完成；新的实机执行尚未发生，Q2 未验收**。

## 现场结论

Owner 回传的原始诊断包经过有限解压、成员长度和 SHA-256 校验。
恢复准备已返回 `RECOVERED_PREPARED`。随后 owner 发行了监督服务启动命令，
其 `systemd-run` 客户端退出 1，stderr 为 `CPU quota '100.0000%' invalid.`。
该次内层捕获 `complete=true`，stdout 为空，stdout/stderr EOF 均齐。
错误属于启动命令编码，不是用户选错脚本或内层输出丢失。

以准确原安装来源重建启动 argv，其摘要与保留的 delivery 记录一致，
其中 CPUQuota 确实为四位小数。原候选仍为
`d581098252c7e6422d798230359510c2ad9b1d8e`，tree
`27a246b92dafc41f9afe0475e2da496865c6797e`；未改写现场安装。

保留记录中没有子服务 InvocationID、子服务结果或封存；前后服务观察均为
not-found，子监督和执行输出不存在。owner reservation、envelope 和 delivery
已经存在，不能把“子服务未创建”改称“请求从未发行”。原 owner 结果仍为
`INCOMPLETE / SUPERVISOR_DELIVERY_UNCERTAIN`，不追认成功。

外层恢复退出 3。旧交付器把非零退出也归入 `complete=false`，所以外层
`RECOVERY_GUEST_CAPTURE_INCOMPLETE` 不能单独证明管道丢失。诊断传输退出 0，
双流齐全。当前树空只能证明诊断时状态，不能补写原 deadline 内的退出证明。
以上为脱敏事实摘要；原机路径、身份、配置和原始证据留在私有材料中。

## 修复范围

这是既有 CLOSED Q2/E1–E3 开发范围中的兼容性修复，延续 Owner 的修复及提交推送授权。
不执行新的 guest 批次，不修改已批准恢复三份文档、旧候选、旧账本或旧 reservation。

| 路径 | 改动及约束 |
| --- | --- |
| Q2 supervisor / owner | CPUQuota 使用整数编码，百分数最多两位小数；两个新 delivery producer 都声明编码版本 |
| controller / launcher / preparation | 声明精确值必须为 100 微秒/秒的整数倍；不可表示值在副作用前拒绝，不擅自取整 |
| 普通 jobs runner | 按完整运行与停止窗口计算比例，在 systemd 可表示精度上向下取整；保留原 0.1% 下限 |
| 离线 evidence review | 无格式标记的历史记录仍重建原四位文本；新版只接受明确 `systemd-percent-hundredths/v1`，不改写旧摘要 |

修复同时清除了普通 runner 的六位小数输出及 preparation 的浮点输出。
参数比例不会因序列化向上扩大；这不等于已证明真实内核调度的累计 CPU 消耗。

## 独立解析与回归

本机 systemd 为 `255 (255.4-1ubuntu8.17)`。测试通过 ctypes 调用真实
`libsystemd-shared-255.so` 的纯函数 `parse_permyriad_unbounded`，不启动服务，
不连接 manager，不修改 cgroup。旧 `100.0000%`、六位小数与三位小数均返回
`-EINVAL`；新版精确编码及 runner 输出通过，并与期望整数比例一致。

对应的固定上游来源：
[systemd 百分比解析器](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/basic/percent-util.c)
和 [CPUQuota 属性处理](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/shared/bus-unit-util.c)。
源码与现场错误一致：该解析器不接受超过两位的小数，即使多余位都是零。

17 个受影响测试文件共 **297 passed、1 skipped，16.52 秒**。覆盖 jobs runner、
controller、launcher、preparation/driver/delivery/recovery、assembly、chain、
supervisor 和 evidence review。新增 13 项测试全部实际执行，包括真实 C 解析器。
唯一 skip 是普通 runner 的真实 systemd/cgroup 集成环境不可用；不记为通过。
`git diff --check` 通过。

证据负例通过完整 sealed bundle 的 `review → facts` 路径：删除新版标记、
null/未知标记、旧摘要错标新版、新版不可精确表示值均拒绝；旧版四位历史包
仍保留原离线一致性合同。离线一致性不等于真实 host provenance 或 Q2/Q3 验收。

## 下一次真实执行的边界

修复已发布到 `main`：公开 commit `9a556322183f0fa80d4edeada4b03c74a26524a5`，
本地同字节 commit `5c4c07a3cea58db2660be9f1f9322ddbafdfefbe`，相同 tree
`0687d7cd8eaf6a901d565a60b99042827437354c`。
从验证过的准确公开 Git commit 对象离线构建 wheel，大小 265979 字节，SHA-256
`0924ac531f3f710cd39838318e8d72b09a4261589df70cf3f650be62a8c8ebcb`。
53 个 payload 文件逐项匹配 committed source；独立 venv 安装后 broker/MCP 的
source 与 payload 身份一致。可选 MCP SDK 未安装，未声称真实 MCP 会话通过。
构建、安装与 provenance 检查均 PASS，仍只是离线候选验证。

本次没有重跑原 recovery/owner，没有换名发行或刷新旧期限。
原批准恢复的 R05/R06/R07 固定旧候选、只允许未发行的首次运行且禁止自动重试；
其一次 300 秒窗口已经结束。修复后的候选替换和新的运行窗口因此需要明确的新范围，
而不是重新询问原范围内的单项修复。

新范围应一次覆盖准确状态鉴证、保留旧材料、独立候选安装、新运行身份及完整退出/EOF
复核，并在文档基线获批准后整批实施。任何旧对象已消费、容量不足或身份不明应停止。
Q2/Q3、production、GX10 及 E4–E6 的既有验收状态均未改变。
具体新范围见 [单次新运行提案](q2-cpuquota-retry/REQUIREMENTS.md)，当前仍为 OPEN。
