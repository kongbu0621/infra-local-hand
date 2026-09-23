# E3 quota Q1 原生查询原语验证

日期：2026-09-23。**仅完成 Q1 内部 ABI 原语；Q1 总体和 E3 实机验收均未完成。**

## 准确来源和批准顺序

| 项目 | 固定值 |
| --- | --- |
| R | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` |
| A | `415327ebdcc251bb055da9931a7a88990f750b7a` |
| B | [Owner 原话及上下文](../governance/E3_QUOTA_HARNESS_OWNER_DECISION.md)，事件 `LH-E3-QUOTA-HARNESS-CLOSURE-20260923-01` |
| 独立 CLOSED 记录 C | `5a4ea852091db06549a876e42bbd5f95d5869d3b` |
| 准确实现 D | `eb7ca61d109f00a699de8591fcf0e0f92717019b`，父提交为 C |
| 实现 tree | `3195b29c9a4261e521899e4b1439878a87d1ed0e` |

新 A 的三份文档逐字节未改。C 只有批准副本与状态登记；D 才加入源码/测试。
实际测试字节与 D 的四个新增源码/测试/说明文件逐项摘要相符；发布 tree 与本地 index 一致。

## 本检查点实现了什么

[原语与准确接口](../../tools/admin/local_hand_quota_observer/README.md) 位于独立管理侧开发目录。
零参数，仅从管理父进程继承的固定 FD 观察；无任意路径、项目 ID、修改动作或降级查询入口。
使用系统 headers 的 quotactl_fd ABI，固定检查 project accounting/enforcement、generic hard limit、
有效位、零值和字节换算溢出，保存每步原 rc/即时 errno 及前后 root/project/enforcement 事实。
身份变化或后续复查失败保持不明，清理错误不覆盖原错误；报告有界且不构成准入许可。

这是内部查询原语，完整 observer、受保护 manifest 准入、peer 鉴权、请求账本、最小权限过滤、
独立监督与预算装配均尚未实现。没有安装、提权、接入 broker 或改变普通作业的 namespace。
没有把管理产物或测试 shim 纳入默认 wheel/Plugin；现有显式包列表和普通 job 代码未修改。

## 验证与准确限制

| 验证 | 结果与覆盖 |
| --- | --- |
| 原生编译 | 云端 Linux x86_64，系统 C compiler，严格 warning/error、conversion/format 检查通过；105 个编译输入/headers 有摘要记录 |
| 定向 unittest | 9 项通过；含真实 binary 无 FD/拒绝参数/输出失败负例，以及 link-time 模拟的配额查询分支 |
| UBSan | 33 个明确模拟场景通过；覆盖单位/整数边界、权限与不支持 errno、身份/继承/enforcement 漂移和清理错误 |
| 证据记录 | 37 组命令的原始退出码、stdout/stderr、时间和摘要；非零负例依其期望保留，不转写为 exit 0 |
| 真实 quota syscall | **0**；真实 binary 负例在查询前拒绝，所有 quota 成功/失败 syscall 分支均由 test-only shim 模拟 |
| GX10/aarch64/真实 hard quota | 未编译或执行，BLOCKED/UNVERIFIED；不能沿用云端 x86_64 结论 |

首轮编译发现 QCMD 宏的有符号整数转换，保留错误转录并明确标注 TRANSCRIPT。
修复为在宏运算前将子命令转为 unsigned，后续严格编译和 UBSan 覆盖对应数值边界。
没有把工具界面中的错误转录伪装成原重定向日志。

前后观察不构成原子快照或未来持续保证；ext 系列共享 filesystem magic，只作预筛。
准确 mount/boot/namespace/generation、admitted limit、原执行和预算绑定须由后续装配补齐。
Q_GETQUOTA 可能阻塞及涉及 quota 元数据，不能将本二进制单独提权运行来替代受监督装配。
真实超限写入、普通身份/管理身份差异和全部 H01–H13 均没有获得本轮 PASS。

## 私有证据

| 项目 | 值 |
| --- | --- |
| ZIP | `infra-local-hand-e3-quota-q1-eb7ca61-evidence-20260923.zip` |
| 大小 / 成员 | 58,097 bytes / 83（含 MANIFEST.json） |
| SHA-256 | `d194b05717129cf670256c80caa327518fad93235f0867ddc4253fc42e178e10` |
| MANIFEST SHA-256 | `7c162275e5f69a0e094b883fe1ccf645bd539bda95abce66bcb2108cf8fcad75` |
| 原生开发 binary SHA-256 | `bc7d2d210ed7fce64fa0886e0e4b0f7f3c6e2a924603533b21d6ca56628e6a5b` |

已核对 CRC、成员唯一性及逐成员大小/摘要。包内含未安装的云端开发 binary 和明确标记的模拟 binary，
供审计而非 GX10 部署；源码由固定 D 定位。原始证据保持私有。

## 下一步与 Owner 分工

本次批准已足以继续该隔离开发范围，无需 Owner 重复确认或反复提供同样的主机库存。
下一步补 Q1 管理侧固定对象准入、最小权限与独立监督装配；准确实现和装配清单就绪后，
再由已有管理入口准备专用 fixture，验证真实 ABI、权限差异和硬限额。
只有原始事实成立后再进入 Q2/Q3。当前没有需要 Owner 在 GX10 执行的新命令。
E4、E5/S2、E6 和现役服务切换保持原边界；生产支持封堵不变。
