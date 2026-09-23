# E3 只读准备检查点验证

日期：2026-09-23。结论：**只读盘点工具与验收交接已完成；E3 实机仍 BLOCKED，候选不可部署。**
本轮未修改产品四包、Plugin、依赖或生产 support；未执行目标宿主、真实 NAS、客户端连接或服务切换。

## 准确来源与范围

| 项目 | 身份 |
| --- | --- |
| 已推送 main 的准备源码 | `287f6b92408ee43b7898acefba48eb226160e6fe` |
| Tree | `b7b2cd4da5e4dd846ceebbbee6fc237cf2140ba7` |
| Parent | `39d45a1c652289949f683e69c8ebb6bfff944bb1` |
| 独立脚本 | `tools/probe_e3_host.py`，30,716 bytes |
| 脚本 SHA-256 | `92eb83cd024826b2cce62f91ee42a28df6c4e0ad326b3b5c919f65e4d9dcc094` |
| 脚本 Git blob | `7893ad946249cd5eff2572a0502508db18f88f8b` |

三份权威文档逐字节匹配已批准 A `79f73faedcd9cde4164b0d1625782dae27db6c2f`；
R 仍为 `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，本轮再次读取直接固定规则并匹配既有完整性摘要。
实现保持为独立 CLOSED 记录 C `367632126c1930983a06b1854f63789448633148` 的后裔。
现有 E1–E3 授权未扩大，E4、E5/S2、E6 未关闭。

本轮交付：

- 标准库独立只读探针，固定 proc/sys 观察与 systemctl/systemd-run 只读查询；完整替换子进程环境、双流总量上限、超时及有限清理。
- cgroup 目录与文件 nofollow、实际 FD mount ID 核对；mount target 仅作词法匹配；不输出 mount source 或原始命令 stderr，不执行 quota syscall。
- 固定三个 false 和未验收 blockers，记录脚本摘要与 boot ID；exit 0 仅表示报告生成，不存在自动启用生产的路径。
- [准确实现缺口](E3_IMPLEMENTATION_GAPS.md)、[只读入口及 H01–H13 后续验收清单](E3_HOST_ACCEPTANCE_RUNBOOK.md)、[NAS 私有输入空白模板](NAS_PRIVATE_INPUT_WORKSHEET.md)。
- 18 个 Linux 专用边界测试；CI 路径触发、范围识别和编译纳入独立探针，后续只改该脚本也不会漏掉验证。

## 验证结果

| 验证 | 结果与准确范围 |
| --- | --- |
| 干净准确源码，定向测试 | **18 passed、0 skipped，0.93 s**；启用 `-W error`，覆盖只读输入、未知状态、脱敏、有界双流、timeout、清理及 FD/mount 边界 |
| 仓库外独立执行 | 从 `/tmp` 以 Python 3.12.14 `-I -B` 执行准确脚本，exit 0、stderr 0 bytes，JSON 3,164 bytes；脚本摘要匹配，结果 **BLOCKED** |
| 兼容性范围 | Python 3.9 grammar 解析通过；未运行 3.9 解释器，不将语法检查称为该版本完整实跑 |
| Linux CI 源码 | **883 passed、1 skipped，356.37 s** |
| Linux CI 独立安装 | **94 checks、292 commands，PASS** |
| Windows CI S1 源码 | **211 passed、154 skipped，383.58 s**；新增 18 项均因 Linux-only 明确跳过 |
| Windows CI 独立安装 | **10 checks、10 commands，PASS** |

准确 [push/main CI run 35846205021](https://github.com/kongbu0621/infra-local-hand/actions/runs/35846205021)，
attempt 1，head 为上表 `287f6b9`，整体 SUCCESS。Linux/Windows job 分别为
`107132921210` / `107132921239`。记录含 run/jobs 元数据、完整 job 日志及产物元数据；
产物摘要来自 GitHub API，本轮未额外下载二进制产物作独立字节复验。
本轮没有重跑旧候选的本地全量或安装态 MCP 检查，不将旧报告计数沿用为新增验证。

当前云端 scratch 的实际基本条件不满足：root 身份、PID 1 非 systemd、cgroup 只读、用户 manager 查询失败，
根挂载观察为 overlay。真实目标主机的当前执行入口尚未绑定；不据此宣称 PRO6000/GX10 已被盘点、离线或具备 E3 条件。
三个授权／验收字段均为 false，真实 harness 未运行。

## 保留的失败与修正

开发阶段先有 6 项基础测试通过；首次扩展矩阵为 15 passed / 1 failed。
原因是测试用的截断 mountinfo 仍恰好满足语法，错误预期为 INCOMPLETE；改为明确缺少必需字段后
16 项通过，再补两项已确认修复的回归，冻结前为 18 passed / 0.95 s。
原失败日志和阶段摘要均保留，准确提交上的最终结果另记为上表 18 passed / 0.93 s。

审阅还纠正了真实边界问题：slice 不要求 `Delegate=yes`；根 cgroup 不要求只在 non-root cgroup
存在的 type/events/CPU/memory/pids 文件；关闭父 FD 失败时仍清理新子 FD且不重试旧 FD；
显式空 cgroup/slice 参数被拒绝。固定官方来源与语义见验收清单及实现缺口文档。

## 私有证据与下一步

私有证据包 `infra-local-hand-e3-prep-287f6b9-evidence-20260923.zip`：

- 59,567 bytes，29 members；ZIP CRC、唯一成员名、逐成员长度及 SHA-256 均已核对。
- ZIP SHA-256：`093ecf544c2e4c2bd8ab387e9def7b9f17b59d6bc609c466736bf8033a626f42`。
- MANIFEST SHA-256：`79cd1683207f1a8e2ef03b60db174a2132b6f2fcfa9f53632a4771db50855ccb`。

包内 `LOCAL_HOST_HANDOFF.md` 固定本次提交和脚本摘要，可交给测试机上的 Codex 完成只读采集并回传
JSON、stderr、退出码、来源和时间记录。真实机器原始证据仅私有交付，不提交 Public。

下一阶段先取得目标宿主事实并解决本地 quota 查询机制与隔离权限的冲突，再补真实三 unit harness
及原 namespace 下的准确 errno 取证，按 H01–H13 实测。不能靠换一台 systemd 主机、给 slice 设 Delegate、
提权、放宽 PrivateUsers/PrivateDevices 或移除 `E3_SUPERVISION_UNVERIFIED` 完成验收。
NAS collector、writer 计费身份和限定网络仍未实现／准入，填写工作表不启动真实查询。
