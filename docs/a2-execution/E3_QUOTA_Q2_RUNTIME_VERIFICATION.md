# Q2 第三批验证与接续记录

日期：2026-09-25。**固定源码上的两组回归共 780 项：765 通过、15 跳过、0 失败、0 错误。**
本批同时补齐管理配置/认证通信/多根查询适配、broker 原预算绑定及 bootstrap 回执管道的源码。
完整 phase-close/harness 装配与真实整链验收尚未完成；生产封堵保留。
实现细节与剩余边界见[第三批记录](E3_QUOTA_Q2_RUNTIME_BINDING.md)。

## 准确源码与发布

| 检查点 | 本地提交 | GitHub main 提交 | 相同 Git tree |
| --- | --- | --- | --- |
| 继承的第二批记录 | `7a6033c4a594fd53e7b2d9e77155fd85da758843` | `b0934c2aeb157e550cb49fb7c1ae472bcd1f094c` | `5daa98ea66be97e8d9d82496764cbd372e668bff` |
| 本批准确源码 | `47f2cd3fa03042190e1fffaf2c26ca3fa799664a` | `007cbdf49ca61005c91f092a982a6c9b9240e6f0` | `3e272b5e70cc2f6fc99bf830c2832cd44e05426a` |

源码提交完成且工作树干净后运行下面两组最终测试。通过已授权的 GitHub Connector 发布同树提交；
更新前核对原 main，使用非 force 更新，随后读回确认为 `007cbdf49ca61005c91f092a982a6c9b9240e6f0`。
不同提交 ID 来自本地与 API 提交元数据；tree 相同不等于在另一操作系统重跑过测试。
本验证文档和日志随后独立提交，身份以 Git 历史为准。

## 本地准确运行

Python 3.12.14，Linux 6.18.44。运行区间为
`2026-09-25T09:35:05.177555+00:00` 至 `2026-09-25T09:35:11.923354+00:00`。
两组测试分别在独立 Python 子进程并行运行，命令为：

```sh
PYTHONPATH=tools:tests python -B -W error -m unittest discover -s tests -p 'test_local_hand_jobs*.py' -v
PYTHONPATH=tools:tests python -B -W error -m unittest discover -s tests -p 'test_e3_quota*.py' -v
```

| 组 | 收集 | 通过 | 跳过 | 退出码 | 原始日志 / 命令 |
| --- | ---: | ---: | ---: | ---: | --- |
| jobs | 507 | 493 | 14 | 0 | [日志](validation/q2-runtime-binding-20260925/jobs.log) / [准确命令](validation/q2-runtime-binding-20260925/jobs-command.json) |
| quota | 273 | 272 | 1 | 0 | [日志](validation/q2-runtime-binding-20260925/quota.log) / [准确命令](validation/q2-runtime-binding-20260925/quota-command.json) |

日志 SHA256：

- jobs：`13f3871b5d86dac433014b9d373f61a369219ca5c89bf03cb2a21e6b737169da`
- quota：`08742661c21c85af812c0f52542c32428850fd55c719c475872f730ade561e38`

新增两文件共 20 个测试方法，最终运行包含在上表中。覆盖原预算不重发、重启不续跑、回执与启动意图
事务绑定、损坏记录不修补、原 InvocationID 停止、截断/过期/缺 EOF、固定能力和资源参数、
完整多根 ABI/原 errno 校验、session 永久消费、私有证据文件及重复派发阻断。

| 事实层 | 本批证据 |
| --- | --- |
| SQLite、文件、匿名管道 | 使用真实 SQLite 事务、临时文件、fsync、FD 和真实子进程 stdout；EOF 来自 OS 零字节读取。管理员所有权在可移植文件测试中明确建模。 |
| socketpair / SCM_RIGHTS | 本执行器允许匿名 Unix socketpair，实际传递 FD 并检查 CLOEXEC；这不等于命名 listener 或跨 PrivateUsers 服务已经验收。 |
| 命名 AF_UNIX | 创建返回 EPERM；14 项相关命名 socket 测试跳过（旧 jobs 13 项、新 listener 1 项）。没有重试权限升级或用模拟冒充通过。 |
| systemd/cgroup 集成 | 1 项真实集成跳过；PID 1 非 systemd、无既有专用委派及固定非 root 身份，生产 `E3_SUPERVISION_UNVERIFIED` 仍在。 |
| 管理监督、peer、native 结果 | 对固定命令、身份和退出行为作明确模型测试；本轮没有运行真实 quota syscall、跨 user namespace 认证、guest 实验或完整 helper 链。 |

这是相关两组完整回归，不是全仓库本地测试或新的 Q1 实机证明。

## CI

上轮准确 main `b0934c2aeb157e550cb49fb7c1ae472bcd1f094c` 的
[run 36114173591](https://github.com/kongbu0621/infra-local-hand/actions/runs/36114173591)
已核实 classify、Windows、Ubuntu 三项成功；只适用于上轮。

本批准确源码 `007cbdf49ca61005c91f092a982a6c9b9240e6f0` 已触发
[run 36119356829](https://github.com/kongbu0621/infra-local-hand/actions/runs/36119356829)。
本记录写入时 classify 成功，Windows 和 Ubuntu 尚在运行；未把 pending 转成 PASS。
后续接续时先核对该 run 的 head SHA 及各 job 结果，再决定是否存在需要修复的具体失败。

## 保留的中间失败

以下是工具观察摘要，不声称保存了它们的完整原始日志：

1. 早期新增 fixture 的 UID/预算声明不符合已有受保护路径与分配合同；修正明确模型及原预算 fixture，
   生产身份检查未放宽。真实接收时 `MSG_CMSG_CLOEXEC` 标志回传曾被误作异常，现只忽略该已请求标志；
   仍拒绝截断、其他标志和外部 FD。listener 的实际 GID 参数也与 endpoint 声明对齐。
2. 原预算校验假定“有 phase budget 必有 EXECUTION_INTENT”，与新增先持久准备再绑定的流程冲突；
   增加显式版本、原 QUOTA_PREPARATION 事件校验，不退款或重新发预算。
3. 一次定向命令写了不存在的 `test_local_hand_jobs_systemd`，收集报 ModuleNotFoundError；
   改为实际 `test_local_hand_jobs_runner`，随后最终按文件族发现运行。
4. 新增不可变观察测试曾在既有 SQLite 事务中调用无 tx 参数的读取，产生嵌套事务错误；
   测试改用原事务读取。修正后定向 63 项为 61 通过、2 跳过，再得到上表固定提交回归结果。

## 下次直接接续

1. 从本报告准确源码继续，不重复 Q1 只读盘点或旧 writer/query；核对 main/CI，保留所有历史失败。
2. 完成受信 phase-close 收集装配：包括独立 admission、listener/collector 的原身份、客户端、EOF 和
   管理父树空证据。现有五项关闭合同不能用普通输入自证新 admission 已停止；未闭合前后继阶段继续拒绝。
3. 将已提交原预算和 root allocation 绑定到固定 fixture 配置、准确 bootstrap 命令摘要、有限 grant 表和
   create-only session，形成一次组合验证输入。配置来自现有明确隔离 fixture，不提供宿主 provisioning。
4. 在明确提供的 systemd/quota VM 中完成认证 IPC、多根观察、三单元资源隔离、原期限与全部退出的
   Q3 正常链，再进入 Q4 故障/恢复；Q2 未关闭和实机证据缺失均分别记录。

R/A/C、旧 UNKNOWN/INCOMPLETE、原 reservation 和容量约束不因本批源码或测试通过而改变。
