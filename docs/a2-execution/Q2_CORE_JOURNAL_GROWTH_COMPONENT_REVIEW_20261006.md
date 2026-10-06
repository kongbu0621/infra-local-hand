# journal 扩容组件交付与未就绪边界

日期：2026-10-06。Scope `LH-Q2-CORE-JOURNAL-GROWTH-v1`，J1–J3。
结论：**J1 部分实现，J2 仅组件验证，J3 NOT ISSUED；没有扩容现场结果。**
这不是 J1/J2 完成声明，也不是下一批业务授权。

## 准确版本和批准链

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，本轮完整读取直接固定来源。
- A：`59948ec4fedb807a31cdbff77acc134e84414160`，三份文档及历史 OPEN 字节不变。
- B：[原文记录](../governance/Q2_CORE_JOURNAL_GROWTH_OWNER_DECISION.md)，事件
  `LH-Q2-CORE-JOURNAL-GROWTH-CLOSURE-20261006-01`。
- 独立 bookkeeping-only C：`6493b1ae035dfa852952165046417c78f0f5383c`。
- 组件 D：`780023e34368cc3a7d91276e19e859ec13603014`，直接继承 C。

D 的新增实现文件分别为 20016 B、9036 B，均在各自 65536 B 源码界内。
批准范围没有变化；未建立另一个变更 A，也不需要重复批准这部分实现。

| 文件 | SHA-256 |
| --- | --- |
| `tests/e3_host/q2_journal_growth.py` | `fa63da4971e8b8d2334757365c557348a04cc9c4c4934e5bd383d2b972a0bf1c` |
| `tests/e3_host/q2_journal_growth_guest.py` | `2e1d4d7af215ba6b6bad748b1db6f8f051979c7aa4854cc7cd64dbb736c85371` |
| `tests/test_e3_q2_journal_growth.py` | `5012ff56b4e22a1c51f457f21904c86eebcb8a55fdda665956ed24c7a6828fde` |

## 已交付的组件

- 固定名称 create-only 输出、并发 marker 排他、预算检查、终止后不恢复的顺序状态机。
- 完整流式备份、fsync、独立重读摘要；保留失败产物，不自动删除或还原。
- 无 force/share/shrink/repair 的 qemu-img 参数、镜像信息拒绝条件。
- 持有 pidfd、启动标记、准确 argv 和 executable identity 的进程检查；未知/额外 writer 的结果校验器。
- 有界输出和不强杀 mutator 的观察器；逾期保留进程句柄，不以断流证明远端退出。
- journal 内容树的有界 no-follow/O_NOATIME 检查、内容及权限/链接/mtime 保留比较；
  unit 静止/启动边、必要证据持久文件系统及最终五 parent 的校验组件。
- 原固定启动脚本仅变更新 pidfile 和 serial null 的参数转换；不执行原脚本。

这些是可测试组件，不是完整现场 dispatcher。命令行即使传入 `--execute` 仍在任何现场读取、
marker 或 SSH 前返回 `GROWTH_J2_NOT_FROZEN`，不能通过调用者参数解除。
旧 runtime、wheel、bootstrap、dispatcher、release allowlist、boot 校验及 production E3 未改。

## 验证事实和保留失败

最终窄验证命令：

```text
python -B -m pytest -q tests/test_e3_q2_journal_growth.py tests/test_e3_q2_core_capacity_observation.py
195 passed in 1.24s
git diff --check
```

新增范围 70 项，既有容量观察 125 项。这不是全量来源测试或 CI 结果。
原生合成测试在独立临时目录实际执行 mke2fs/debugfs/qemu-img/resize2fs：
建立 256 MiB ext4、写入 sentinel、转换为 qcow2、完整备份、增长到 512 MiB、
正常 info/check/compare、转换合成 raw 并增长 ext4，校验原 UUID/features、容量和 sentinel。
qemu-img 非 strict compare 验证旧逻辑内容及新增零区，语义遵循
[QEMU 官方工具文档](https://www.qemu.org/docs/master/tools/qemu-img.html)。
此测试是**合成离线 ext4**，不是 guest 在线 resize 支持、正常关机/启动或业务成功证明。
另实际测试本地合成进程的 pidfd、准确 argv 和自然退出，没有操作真实 VM。

保留本轮发现并修复的两项验证失败：

1. 原固定启动脚本尾部包含中文提示，首次按 ASCII 解码失败。改为完整脚本严格 UTF-8，
   执行参数仍严格 ASCII，增加回归；重新对准确原件做本地静态核对通过。
2. 一次组合测试为 184 passed / 1 failed：既有 marker 并发测试的 loser 可能先被
   `CAPTURE_PARENT` 拒绝，而不一定走到 `O_EXCL`。只修正测试接受这个安全拒绝；
   旧生产捕获源码及身份检查没有放宽。最终 195 项通过不抹除首次失败。

## 本地静态工具/argv 核对，不是 J3

当前工具沙箱把部分 root owner 映射成 nobody；经受控的真实宿主本地读取核对后，
使用原 root-owned executable/O_PATH/no-follow/名称-fd 检查。
host 工具按 A 冻结文件身份与版本，不把额外二进制字节读取能力当作 A 新增必要条件。
本轮额外尝试 root-owned 工具的 O_NOATIME 字节读取返回 EPERM，未降级普通读取、未提权或改权限。
guest resize2fs 的完整字节摘要仍必须由原 root helper 在第一阶段取得并在第二阶段匹配。

| 静态绑定 | SHA-256 |
| --- | --- |
| qemu-img 身份/版本组合 | `de0bbac5f63fc299481ee2ff8ace403a3d8703b963a9a58295e0ea55702edd73` |
| qemu-system 身份/版本组合 | `2ffd21be4dc84c2051643d936aeee864a261e1474e7f73726842e746b4d470d2` |
| 新启动 argv | `da196b4942f815ac2a64495f692638cd6901432ef2c438d4fbaf3849c6110517` |

上述不是完整、可发行的私有 J2 manifest；没有验证原 QEMU 当前 argv 或当前写入者。
不以静态脚本推断当前运行事实，也没有因工具环境 PID 1 作出宿主不支持的判断。

## 直接剩余工作与发布状态

J1 尚需把以下代码接成受测闭环：

1. 固定原输入/全部保留原件到 guest 旧域、安装和必要持久证据的准确清单；
   systemd/cgroup/process 当前静止及自动启动关系的真实 reader，未知即阻断。
2. VM 四盘/seed/网络/完整 argv、镜像名称-fd 与实际 writer inventory 的联合绑定；
   一次 nonce/前摘要令牌、正常关机确认、离线锁/备份/增长、一次启动及第二阶段 helper 的 dispatcher。
3. 远端整块设备/UUID/serial/工具绑定、一次在线 ext4 增长、前后树与五 parent 返回；
   双时钟、资源计量及未闭合 mutator 记录贯穿两阶段。

然后才补齐完整 J2 故障注入、准确私有执行 manifest、相关 CI；所有必要门通过后方可 J3。
现有批准对上述原范围仍有效，不应把实现未接齐描述成 Owner 尚未批准。

首次 `git push origin main` 在执行前被权限审查拒绝；没有绕过该拒绝。Owner 随后明确批准将
准确 C `6493b1ae035dfa852952165046417c78f0f5383c` 和 D
`780023e34368cc3a7d91276e19e859ec13603014` 非强制推送到 `origin/main`。
推送已于 2026-10-06 完成，远端 `main` 已核对为 D；对应
[Local Hand v0.1 Validation](https://github.com/kongbu0621/infra-local-hand/actions/runs/37408293031)
在本报告提交前仍为 `in_progress`。CI 尚未结束，因此这里不声称 CI 通过。

现场计数：marker 0、SSH 0、关机 0、真实镜像备份/增长 0、VM 启动 0、H01/Q4/H11 0。
没有维护结果证据收回，也没有新增业务结果；只有本地组件、测试和静态核对证据。
一次 `lhqjgrow-20261006a` 机会未消费。原 UNKNOWN/全额承诺、无重试/补采/清理/自动回滚、
支线暂停和 production `E3_SUPERVISION_UNVERIFIED` 保持。
