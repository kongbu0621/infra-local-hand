# 核心 journal 保留数据扩容实施计划

状态 **PROPOSED / Gate OPEN / NOT APPROVED**。Scope `LH-Q2-CORE-JOURNAL-GROWTH-v1`，仅 J1–J3。
本计划受[需求](REQUIREMENTS.md)和[架构](ARCHITECTURE.md)约束，不授权第五次核心尝试。

## 顺序和具体交付

先提交这三个文档形成准确 A，再登记完整 commit/tree/digests 与 OPEN。
Owner 必须明确接受 512 MiB 目标、整个隔离 guest 的一次正常停机/启动、两次维护连接、
易失状态/boot 变化、新 pidfile/串口 null 的可诊断性取舍、完整备份与非原子恢复、
非排他容量及 mutator 可能超过观测期限的边界。
准确 B 后先独立 bookkeeping-only CLOSED C，之后才有新源码/测试 D；不 squash。
当前只有本地只读事实和方案，没有新 marker、SSH、备份、扩容或停机。

## J1 窄实现

在 `tests/e3_host/q2_journal_growth.py` 与 `q2_journal_growth_guest.py` 实现 host coordinator
及固定两阶段 helper；相应窄回归在 `tests/test_e3_q2_journal_growth.py`。
源码检查基线为 `3412fa65c5fdced51db4254e44dfbc4d8ad9f89b`；两个新增实现文件各 ≤65536 B，
不引入第三方依赖。复用已有安全读取、绑定、受限捕获原语，不运行旧 consumed 入口。
不修改生产、业务包生成器、发行 allowlist 或已通过 locale/sudo 解析。

先接齐 local identity / marker / budget / 状态机，再实现只读 guest 门、关机许可令牌、
离线备份/增长及启动，最后接齐 ext4 增长/内容与容量回收。每步失败只有留存出口。
启动 argv、已有工具的准确文件身份/版本和 pidfile/serial null 差异必须冻结为 D 的私有执行清单，
不能在 J3 当场选择其它工具或增加控制接口。工具不满足合同就是阻断，不现场安装。

## J2 验证和准确冻结

只做本范围窄验证和通常 CI，合成验证不得借用真实 guest 或真实镜像：

- fixed source/plan/capture pins、路径/符号链接/硬链接、权限/owner、pid reuse、多 QEMU 实例、
  镜像替换、父目录替换、未知 writer、前后 drift、未知 boot/自动启动依赖均拒绝。
- O_EXCL 并发只有一 winner；部分 marker、已有备份/输出、fsync 失败、预算不足均不重试。
  本地预检失败零 marker/连接；marker 后失败永久消费；两次 SSH 计数和无探测连接可验证。
- 模拟每个 poweroff/check/copy/hash/resize/start/resize2fs/EOF 失败和超时；
  不能跳过备份、强杀 mutator、启第二 VM、继续下一阶段、使用原输出名或自动还原。
- 在独立临时合成 qcow2/ext4 fixture 验证 256→512 MiB、旧内容与 UUID 保留、零新增区、
  不足/超限边界和工具参数；没有原生条件如实 BLOCKED/SKIP，不以 mock PASS 替代实际工具兼容性。
- 完整固定配置的启动等价性（仅 pidfile/serial null 的明确差异）、无串口文件写入、独立 PID 观察，
  以及关闭本地捕获后可能仍存在的 QEMU/远端进程状态。

提交干净准确 D，保存 source/tool/argv/input 摘要、测试结果和 `git diff --check`，等待相关 CI。
只在 J2 全部必要项通过、无新 material 差异时进入 J3；不为文档提案反复跑全量测试。
任何无法兑现的承诺都先回到文档审阅，不把真实机器当成 feasibility spike。

## J3 条件单次维护

从首次现场本地预检起固定新的 900s 双时钟；重复读取必要 pins 不刷新窗口。
步骤依架构：本地准入 → marker → 第一条检查/令牌/正常关机 → 原 QEMU 退出/锁确认 →
完整备份/校验 → 镜像一次增长 → 一次启动 → 第二条检查/文件系统增长/回收。
这是一轮有两个预先批准连接的维护，不是任一旧 batch 的 reconnect。
任一前置失败即停止后续步骤；已开始的破坏性修改不强杀，逾期按需求报告 UNKNOWN 并停止后续操作。

不关闭/重启任何业务 unit，不关闭 production E3，不改变 SSH、systemd、fstab、配额或权限。
无法证明正常关机不会丢失必要易失证据或触发业务自动启动时，在关机前停止。
备份、原始前后证据和进程状态只留受保护本地；公共仓库只记录摘要、步骤状态、容量及边界。

完成必须同时满足：精确 512 MiB 镜像/块设备、原 UUID/挂载/内容保留、备份完整、
journal 普通可用量 ≥400 MiB/32768 inode、其它原 parent 身份保持、必要步骤成功与完整回收。
不足则不临时扩大到 1 GiB，不清理文件或降低保留空间，不改其它盘，不启动 H01/Q4/H11。
报告原 321 MiB 仅为下一批原预算的条件基础，另列维护承诺/实测及仍 UNKNOWN 的副作用。

## 维护后直接交接

交付新旧 boot 的准确关系、保留数据/镜像/备份、维护费用和完整容量表。
随后才能形成下一次核心验收的准确 A，接入维护后的 boot、四旧核心及两旧诊断与维护的完整保留边界，
同时明确新的 pidfile 与 serial 参数，不以原管理脚本摘要冒充实际启动 argv 未变。
继续原正常链→取消→同账本恢复；不能用本范围批准或虚拟盘变大绕过核心准入。
这次不预设新业务 ID，不提前消耗未来业务 marker，不重复 sudo/locale 专项。
如果 J3 未完成，交付首个失败、已发生修改、仍在运行/未知进程和安全恢复所缺的最小授权，不自动清理。
