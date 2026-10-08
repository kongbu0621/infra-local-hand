# DS1 声明目标检查与接续实现

对应 Owner 已批准的 `LH-Q2-CORE-DECLARED-STARTUP-CONTINUATION-v1`。准确 A
`2b13dd653ca19eaaf46a18e6ffc3f447b62eee59`，独立关闭 C
`a2a6d62de08b2d1d8fbf9da97e8ccf938e3777c1`；本实现直接承接 C。
[Owner B](../governance/Q2_CORE_DECLARED_STARTUP_CONTINUATION_OWNER_DECISION.md) 保存准确原文。
三文档字节及历史 OPEN 标签保持不变，原 R 不变。

维护 pre/post 仅查询声明域的严格属性，取消全量 unit/unit-file/template 枚举和
未知单元引用判定。返回 DECLARED_ONLY，明确未知单元及间接启动均 NOT_PERFORMED。
当前五字段 assurance 与原 QI/GS 四字段历史分开验证，缺项或虚报观察均拒绝。
覆盖缩减及管理前提来自本次明确批准，不能表示为持续排除已获证明。

GuestInventory 的 AST 比较确认仅 startup_manager 改变，删除 template_startup 及其
私有匹配诊断方法；collect 的两次 quiet_service/cgroup、当前进程/FD/maps/writer、
persistent 和数据校验全部保持原样。原 Q1 固定来源与 19/7/7 清单不变。

维护及独立核心消费者同步 08f、guest v3、manifest/receipt v10、短预检 v9、
transition v9、reconciliation/history v13 和 host-capacity v12。保留八代旧窗口的
40 原件、32 缺席名及全部消费/UNKNOWN。九代维护费用为 11664 MiB、3330 inodes、
1080 nominal CPU-s；原核心另计 64 MiB/16 inodes，无退费。
[旧08e五件最小索引](Q2_CORE_Q1_BINDING_ORIGINALS_INDEX_20261009.md) 按本次批准公开；
原文、机器信息和新08f记录仍私有。

## 离线验证

- 保护读取验证16个静态输入、20件原核心失败、4件诊断、4件容量及40件旧维护原件。
  没有新增现场查询、SSH、VM观察或维护 marker。
- 用真实保留来源和新源码核对：descriptor 26393 B，压缩 bundle 38929 B，
  展开 132828 B，远端 argv 54035 B；20位时钟下静态 marker 64518 B（待提交 D
  占位 WORKTREE）。这些是限额验证，不是当前 VM 状态或维护成功证据。
- 受影响核心/维护回归最终合计3116项通过、48项跳过。整组第二次运行3111通过、
  48跳过；剩余5个容量测试的替换数字错误已修正，该文件47项全部通过。
  首轮 fixture 旧协议、漏接 DS 权威和累计容量校验旧常量的失败均保留，不抹掉失败。
- 新用例覆盖声明域查询、pre/post范围记录错配或虚报、五字段保证的两侧验证、
  08e原四字段与七代嵌套历史、准确 R/A/B/C、来源与清单篡改，以及合成成功后
  双消费者接续。实际成功不能由合成数据代替。

## 本提交时的状态

准确 D 的 CI、独立安装、完整核心输入大小核对和两 caller 冻结尚待完成。
DS2 NOT_STARTED，DS3/H01/Q4/H11 NOT_RUN。全部 DS1 验证通过后才执行唯一08f；
完整维护原件 VERIFIED 后才可发行原07a核心包。任何失败 STOP_AND_RETAIN，
不重试、补采、清理或扩展。原所有窗口、预算和期限保持。

## 现场返回后的普通修复

上述为原 D 提交时状态；后续 DS1 已完成、08f 已消费失败，准确事实以
[现场返回](Q2_CORE_DECLARED_STARTUP_FIELD_20261009.md) 为准。本次基于其登记提交
`c2faa34f08541d08333c7d1bfc9efcbd584a9956` 修复现有接线和错误归因，无覆盖变更。

发现一处确定的后续阻断：guest 已生成 `lhq-journal-growth-guest/v3`，host 的
`MaintenanceTransport.receive_report()` 和 `finish()` 仍要求 v2。合成的真实 guest
v3 报告通过 guest 校验后，会被原 host 拒为 GROWTH_REPORT_BINDING。本次两处统一
引用 guest 的 REPORT_SCHEMA，仍只接受准确当前版本，旧历史协议校验保持原样。
该问题尚未在08f触发，因为08f先在进程检查停止；不能冒称它是08f的根因。

进程检查在进入清单和每个PID时更新context，记录PID、观察者PID、已读stat中的
启动时钟及PPID、准确cmdline/exe/cwd字段、cgroup摘要、保护根序号/摘要、匹配内容
字节数/摘要及位置。cmdline另记参数序号、参数内偏移和边界；exe/cwd记deleted后缀
处理。序号中根从1开始，参数和字节偏移从0开始。输出不含路径或参数原文。
命中时尚未进行末尾stat复核，明确identity_rechecked=false，不声称已证明PID稳定。
所有诊断来自原有读取；不新增进程扫描、SSH或子进程。诊断计算失败仍返回原拒绝。
成功后清空context，防止后续persistent失败被误归因进程；FD/maps等保护保持。

验证：相关journal、DS和QI回归568通过、2跳过；最后context清空调整后17项进程
用例再次通过。新增真实guest生成器→host管道测试覆盖pre/post和关机请求确认，
拒绝v1/v2/v4报告及旧v2确认。合成进程用例检查准确分支、读取次数、隐私、原拒绝
和成功路径；独立审查未发现覆盖放宽。没有访问原机或执行真实维护。

源码大小：host81541 B、guest62675 B、reader13357 B，低于原各自上限。
仅合成描述下的pre/post压缩bundle为34848/35867 B，展开105056/109908 B；
这不是私有真实输入冻结或下一窗口准入。08f的原冻结与五件原件保持，不更新pins。

本地Codex下一步限于已有原件和已保存启动命令的离线核对：能否从保留资料把保护根
引用定位到具体启动命令或工作目录；若材料没有该观察，就明确报告缺项，不猜PID，
不再把旧domain/unit当命中者，不停服务或补采。新诊断不能恢复过去未记录的PID。
准确CI另以本次修复提交为准。H01/Q4/H11仍NOT_RUN，现场具体进程未定位；
不能重放08f或发行条件核心包，任何进一步现场动作仍按原R及准确范围处理。
