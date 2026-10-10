# TC1 冻结与 TC2 宿主启动身份预检返回

本记录接续[实现核验](Q2_CORE_TRANSPORT_IMPLEMENTATION_REVIEW_20261010.md)，依据
[准确 A/B/C](../governance/Q2_CORE_TRANSPORT_CONTINUATION_BASELINE.md)的整批批准。
范围内未再次请求逐步骤批准。原 UC2/10a 失败和缺失 receipt 原样保留。

## 准确提交与冻结

- 独立 C：`2bac65db690759bfe89a03228dc3b5186056569d`。
- 直接子 D：`776b9810ec07ed8e1d37d4a740eeff5190c1c15c`，tree
  `7db075ba1cd28c372f70692c9a4265e799feefc7`。C 与 D 分开，没有 squash。
- D 已发布 main；[首次 push CI 38022864156](https://github.com/kongbu0621/infra-local-hand/actions/runs/38022864156)，
  attempt 1，三个 job 全部成功，没有通过 rerun 替换首次结果。
- 不可变 freeze 摘要：`8ff0439838298503957bffc6c6c12672dcee085c2bfd1b4abf3b45955338be28`。
  维护/核心 caller、静态来源读取器、独立维护验收器和离线读取器的五份摘要均已固定。
  归档、原始证据、逐文件索引、caller路径和机器身份保留私有。

| 验证 | 实际结果 |
| --- | --- |
| 本地核心/维护回归 | 3449 passed / 48 skipped |
| 固定来源/原窗口 | 548 passed / 21 skipped |
| 安装权限与新来源拒绝 | 77 passed |
| 实际128 FD/256 MiB custodian及新增归档生命周期 | 44 passed |
| D首次Linux源码CI | 7494 passed / 89 skipped |
| D首次Windows源码CI | 1907 passed / 1381 skipped |
| Linux CI独立安装 | 94 checks / 292 commands，PASS |
| Windows CI平台专用独立安装 | 10 checks / 10 commands，PASS |
| 本地准确D独立干净检出、构建/安装 | 94 checks / 292 commands，PASS |

真实保留来源验证包含原20份核心原件、55份旧维护原件、old09c与old10a两种独立归档，
固定输入19份。原10a十五成员、原freeze/终态和五caller重新核对未变，没有补造receipt。
两个来源消费者及独立dispatcher均通过；历史摘要组未变。各轮本地失败日志仍保留。

准确D的完整形状：marker 63703 B、receipt 44070 B、pre/post描述28470/48655 B、
压缩bundle33694/37114 B、展开143770/165929 B、remote argv47228/51788 B。
transition 51193 B、approved-input 433576 B、短preflight 709 B、核心包上界19475616 B。
全部在原限制内。维护FD交接前122、保守峰值128、交接后含余量90，核心准备上界126。
额外以实际128 FD/256 MiB AS隔离进程复核完整保留来源与显式合成核心数据，通过；
该次CPU约6.10秒、RSS峰值182439936 B。它没有构建或发送真实核心包。

私有调用器合成验证覆盖维护预检失败、执行失败、成功交接、诊断保留及重放拒绝；
独立验收器覆盖完整成功、缺失completion、子退出失败、归档和receipt漂移，读取到的
八原件先保留再作语义验收。核心caller的条件拒绝、合成成功交接及重复调用拒绝也通过。
**TC1 完成**；这些验证本身不证明维护或核心成功。

## 唯一 TC2 实际返回

固定新caller `lhqjgrow-20261010b` 调用一次。它在本地preflight返回：

| 字段 | 原返回 |
| --- | --- |
| state / reason | `BLOCKED / GROWTH_ACTIVATION_HOST_BOOT` |
| error_type / errno | `ObservationError / null` |
| caller exit / phase | `3 / preflight` |
| marker_created / ssh_requests | `false / 0` |
| diagnostic | `{}` |

preflight未通过，因此execute未调用。没有消费marker，没有SSH、poweroff token、备份、
journal增长、维护重启或核心包。没有guest报告或维护completion。六份本地调用返回和
失败记录/终态私有保留；本轮维护原件数为零，没有为了凑集合创造或读取现场原件。
不可变freeze与五caller摘要再次核对未变，终态gate单独更新为
`TC2_PREFLIGHT_FAILED_TC3_NOT_RUN`。

## 仅从已保留返回确定的阻塞

准确D在创建VM工具和固定VM身份之前要求：接管记录的 `host_boot_id` 等于本窗口的
`boot_id`。用已有freeze和本次preflight原返回逐项对比，两个值确实不同；没有追加
宿主/VM/端点/进程或SSH查询。机器标识不公开。这是接管记录与当前宿主窗口的启动
身份不一致；不能由此断言当前VM存在、存活、已停止或位于何处，也不推断改变时间或原因。
现有正确拒绝保持，不能直接替换旧boot字段、复用旧PID或略过身份保护来继续。

**TC2 PREFLIGHT_FAILED / STOP_AND_RETAIN；TC3/H01/Q4/H11 NOT_RUN。**
10b是已调用但未消费维护窗口的预检；它不能被重放。已消费维护代数仍为十二，old09c及
新10b均没有新增消费marker；十四份完整维护义务及核心捕获18208 MiB/5196 inodes不退款。
本批不再发起现场步骤，不重试、不补采、不改VM/服务、不清理、不恢复、不另开窗口。
后续需要针对宿主启动身份变化与当前VM身份给出有依据的有界接续；本次软件验证通过
不能代替该接续的事实与授权。

## 本轮直接修复请求与最小接续准备

Owner随后要求直接修复并推进核心，暂停分支功能。本地只使用既有activation记录、
准确D源码及10b返回核对：启动身份拒绝符合实际保留值，并非可删除的多余检查。
已准备一个私有、单次、有界的宿主读取入口，以确定当前原VM状态和最小恢复动作；
没有新增产品功能、诊断框架或另一组三层文档，也没有改变已冻结维护/核心caller。

具体范围是原固定PID/端口、宿主boot/namespace、已绑定QEMU内容及元数据、五个
配置镜像与另存原system的元数据，以及原资源准入读数。镜像只读元数据；总时限
10秒、单项kernel输出至多64 KiB、QEMU内容读取至多32 MiB、私有结果至多256 KiB，
固定端口监听查询一次，不查其他PID/端口，SSH、VM启停、镜像写入及核心发行均为零。
语法和唯一外部命令的静态核对通过；这些检查不代表现场读取已执行或VM已就绪。

自动审批在工具创建进程前拒绝了该读取，理由是当前失败终态只允许保留证据离线
复核，并禁止新增现场采集；一般修复指令未解除这项限制。未尝试其他通道或间接
执行。没有新现场结果，当前VM存在性、存活和端点状态仍为UNKNOWN。
准确拒绝、读取方案和源码摘要保留私有，状态为待明确批准、未执行。

下一项需明确批准的是上述一次固定宿主读取。若之后证明VM不存在且端口未监听，
再依据实际当前绑定准备准确的单次原配置启动；若VM存活，准备核验后的身份接入。
本读取提案不授权任一路径的变更、不修改旧boot、不恢复10b窗口。TC2终态、十四份
义务及H01/Q4/H11 NOT_RUN保持，不将这次审批拒绝计作维护消费或现场预检失败。
