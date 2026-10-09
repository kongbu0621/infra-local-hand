# UC1 冻结与 UC2 现场返回

本记录对应 [UC1–UC3 已批准批次](../governance/Q2_CORE_USAGE_CONTINUATION_BASELINE.md)。
Owner 已回复“批准整批”，批内步骤未重复请求确认。A 的三份原始文档及历史 OPEN 字节、
独立闭合提交 C、原规则 R 和全部历史失败保持不变。

## 执行候选与 UC1 完成证据

准确 D 为 `8f7a438d8a88c98d85852ebfdb6978c5c7bf9230`，tree
`118aeaad621e7aa88a9b60836f6cacb196db4590`，是独立 C
`2a4282800eaae404ff3163446cc06297ce99526a` 的直接子提交；两者未 squash。

- [D 的首次 push CI 37969352546](https://github.com/kongbu0621/infra-local-hand/actions/runs/37969352546)，
  attempt 1，三个 job 全部 success。Linux 7430 passed / 89 skipped；
  Windows 1864 passed / 1376 skipped。两平台独立安装步骤均通过。
- 本地同一 D 的干净检出、独立构建和安装验收为 94 checks / 292 commands PASS；
  wheel metadata 与报告绑定该 D，未改变现场安装。
- 相关核心/维护测试按原 fixture 权限分别运行：3379 passed / 48 skipped / 6 deselected，
  原 022 umask 的六项安装路径测试另行 6 passed；合计 3385 项通过。保留此前测试失败。
  另有 107 项来源/归档/转换测试通过，不把重复覆盖加进独立计数。
- 保留源核验涵盖 13 份源码、18 个固定输入、20 份旧核心原件、55 份旧维护原件、
  既有 30 件 VM 激活返回，以及 old09c 的九成员私有归档。该归档包含六份本地返回及
  原 freeze、执行结果、终态 gate；没有伪造 old09c 的维护五原件。
- 维护与核心调用器、来源读取和独立验收脚本已冻结。合成调用器检查覆盖预检失败、
  执行失败、成功及重放拒绝，核心 gate 在维护未完整通过时拒绝准备真实核心包。
- 真实隔离 FD 生命周期覆盖初始 121/122 个描述符；原 128 上限不变。维护交接峰值
  128，交接后父进程含余量 89，custodian 上界 64；核心准备上界 125。

发行前有界形状如下，属于离线核算，不能代替现场结果：

| 对象 | 字节数 | 原上限 |
| --- | ---: | ---: |
| marker 静态形状 | 59138 | 65536 |
| 成功 receipt 保守形状 | 43111 | 65536 |
| pre / post 描述 | 28470 / 48655 | 各 65536 |
| pre / post 压缩 bundle | 33696 / 37118 | 各 49152 |
| pre / post 展开 bundle | 143770 / 165929 | 各 393216 |
| pre / post argv | 47228 / 51792 | 各 65536 |
| 核心 transition | 46749 | 65536 |
| approved-input 完整合成形状 | 428090 | 1048576 |
| 核心包保守上界 | 19471793 | 33550320 |
| 短 preflight | 709 | 4096 |

十三份维护义务保留 16848 MiB / 4810 inodes / 1560 CPU-s；加原核心捕获为
16912 MiB / 4826 inodes。该数目包含未消费的 old09c 全额义务，不代表十三次现场消费。
单窗时钟、CPU/RSS、AS/FD、控制子进程、VM 限额和原保护均未改变。

不可变私有 freeze SHA-256：
`3f9a4b2941a4926f23345cd8f93efa82e9724070ed10f60d68d836814bed6eee`。
首次 Windows 日志获取遇到 gh 本地 zip 缓存错误，冻结时已验证的 CI job/step 元数据
仍为 success；后续从同一已完成 job 获取日志并单独固定补充索引，未重跑 CI 或修改 freeze。

## 唯一 UC2 返回

固定 `lhqjgrow-20261010a` 调用器只启动一次。preflight 为 LOCAL_PREFLIGHT_PASSED，
随后用原时钟、nonce 和 manifest 执行一次 execute，返回退出码 3：

| 字段 | 实际返回 |
| --- | --- |
| state / reason | `UNKNOWN / GROWTH_USAGE_UNKNOWN` |
| marker_created / ssh_requests | `true / 1` |
| diagnostic operation / stage | `management_usage / live_child_observation` |
| failed child stage / reason | `process_identity / GROWTH_USAGE_IDENTITY` |
| error_type / errno | `ObservationError / null` |
| already held argv digest / starttime | `null / null` |

失败 PID 已保留在私有诊断，未公开。最后有效用量不等于失败样本，也不能证明失败时
已完整计量。该错误来自本地资源计量身份接线，不能写成 CPU/RSS 超限或 guest 保护拒绝。

只保护读取五个固定的已捕获返回位置：实际存在四份，即消费 marker、事件、pre stdout
和 pre stderr；两份 pre 流均为空，receipt 不存在。四份原件已私有保留并固定大小/哈希，
缺失 receipt 明确登记，未补造文件。marker 的 manifest、摘要、nonce 和 D 与冻结预检
完全一致。事件记录 CONSUMED 返回、GUEST_QUIET 开始及 pre 传输；未记录完成的 guest 报告。
没有进行额外进程/guest 查询。

源码与现有事件确认没有发送关机 token，没有进入备份、journal 镜像/文件系统增长或
维护重启。SSH 子进程确实已创建，但没有留存其完整退出状态或 guest 行为；远端结束、
guest 阶段及动作仍 UNKNOWN，不能从空流推断它从未执行。没有 coordinator completion。
核心包未构建或发送；UC3/H01/Q4/H11 全部 NOT_RUN。

私有 gate 已转为 `UC2_CONSUMED_FAILED_UC3_NOT_RUN`，原 freeze 与五份冻结脚本不变。
现在十二代维护已消费；old09c 仍只是已调用而未创建维护 marker 的预检。原十三份全额
维护义务、所有旧 UNKNOWN、私有原件和历史失败保留。

**UC1 COMPLETE；UC2 CONSUMED_FAILED / STOP_AND_RETAIN；UC3/H01/Q4/H11 NOT_RUN。**
不重放任一调用器，不把条件核心当作独立许可，不追加现场采集、重试、清理、恢复或
新窗口。本次消费不因后续代码修复或测试通过而恢复。

## 返回后的普通修复

准确 D 的 `management_usage()` 对每个活跃非 VM 子进程校验已持有的 Popen PID/start。
`Command` 初始化 PID、argv 摘要和 starttime；`MaintenanceTransport` 在创建 SSH Popen 后
直接加入同一 COMMANDS 列表，却没有该身份对象。因此 preflight 使用的普通命令通过，
实际 pre 传输到资源采样时被拒绝。失败返回保留的阶段和空身份字段与此缺陷一致。
后续封存/最终采样仍会遇到同一缺陷；本次 receipt 缺失如实保留。

修复仅在传输子进程加入列表之前，用已创建的 Popen PID 和原 argv 初始化身份，start
保持未绑定。原有单份 stat 采样继续绑定并核对 start、CPU 和 RSS；不增加读取、等待、
重试、扫描或例外，不修改未知资源拒绝、身份漂移拒绝及资源上限。

新增隔离回归用本地 Python 管道对端直接经过真实 MaintenanceTransport 和 Usage，覆盖
pre、post 正常完成及身份漂移拒绝。每个案例在独立进程内使用真实内核计量、原 128 FD
与 256 MiB AS 限额；没有 SSH、现场路径或 guest 操作。首次四项均复现旧缺陷，修复后
正常阶段完成，身份漂移仍在发送 token 之前拒绝；首次采样只读取原有的一份 stat。

六个相关文件合计 197 项通过。首次沙箱运行有 173 项通过，另 24 项既有 custodian
生命周期测试因 Unix socket 发送被沙箱拒绝而失败；同一份 38 项 custodian 测试随后在
普通用户原生环境全部通过，未改变权限校验或生产代码。失败日志保留。修复后宿主源码
96496 B，仍低于原 98304 B 上限；差异检查通过。

源码修复不代表维护或核心通过。准确修复提交及其自身首次 CI 结果独立记录，不能拿
执行 D 的成功 CI 代替。保留当前失败现场，仅允许继续基于现有返回和源码做离线修复。

## 准确修复提交验证

修复 `e96230684450daefc693e8fbe91b1b6dff7b1da4` 已发布 main。它继承执行 D，
生产变化仅为传输身份的一行初始化；没有改变冻结执行候选或旧调用器。
该修复的 13 份准确源码核验通过。独立干净检出、构建和安装验收为
94 checks / 292 commands PASS，wheel metadata 与验收报告均绑定此修复提交。
这些本地隔离检查没有改变现场安装或执行新的现场步骤。

[修复首次 CI 37972467273](https://github.com/kongbu0621/infra-local-hand/actions/runs/37972467273)
attempt 1：Windows 全部成功，1864 passed / 1376 skipped，独立安装成功；Linux 为
1 failed / 7433 passed / 89 skipped，安装步骤未执行。唯一失败来自已有的传输构造
故障 fixture：它返回的假 Popen 没有 `pid`，因而在预定的管道注册故障之前抛出
AttributeError。该失败保留，不重跑覆盖。后续只给 fixture 补齐真实 Popen 固有的 PID
字段；生产初始化和所有拒绝条件不变。后续提交使用自己的首次 CI，旧本地安装结果
仍准确标为 `e962306`，不冒充后续提交的独立安装结果。

fixture 修正后的相关两文件为 37 passed。最终提交
`b65ecb36a166d54e84dcb1ddffb0a64302c40c7d` 的
[首次 push CI 37974131840](https://github.com/kongbu0621/infra-local-hand/actions/runs/37974131840)
attempt 1，三个 job 全部 success：Linux 7434 passed / 89 skipped，Windows
1864 passed / 1376 skipped；准确检出检查和两平台独立安装验收均成功。
Linux 安装为 94 checks / 292 commands，Windows 为 10 checks / 10 commands。
完整 CI 原始日志、job/step 状态、准确提交绑定和最终验证索引均私有保留。

最终核验确认：原不可变 freeze、五份调用脚本及四份现场返回未改，gate 仍为
`UC2_CONSUMED_FAILED_UC3_NOT_RUN`。没有现场重试或核心包；代码修复已验证，现场维护
仍未完成，H01→Q4→H11 仍 NOT_RUN。本次补记只登记验证结果，不修改实现或增加窗口。
