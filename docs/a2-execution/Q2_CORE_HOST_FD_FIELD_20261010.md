# FD1 冻结与 FD2 本地预检返回

本记录对应 [FD1–FD3 闭合范围](../governance/Q2_CORE_HOST_FD_CONTINUATION_BASELINE.md)。
批准的三份 A 文档及历史 OPEN 字节、独立 C、原来源和全部历史失败保持不变。
执行发生于 2026-10-10（Asia/Shanghai）；固定 session 仍为已批准的 `lhqjgrow-20261009c`。

## 准确候选与发行前证据

最终 D 为 `5db76ed8ad6f336dd5daf2401635c6be7a637d3b`，tree
`a20bf680b8f3d975248a91b251fc7502729b5f46`，继承独立 C
`26a89a1a11a958c24987eb590944331a9769b2ad`。首个实现是 C 的直接子提交
`b7fa3745bfd188a37ab6e740cdf5cdd0d440978d`；后两次修正只涉及测试及记录。
没有 squash C 与实现。

- [D 的首次 push CI 37956062125](https://github.com/kongbu0621/infra-local-hand/actions/runs/37956062125)，
  attempt 1，classify-change、Linux、Windows 三项全部成功。
- Linux 为 7332 passed / 89 skipped；Windows 为 1833 passed / 1369 skipped。
  两平台独立安装验收步骤均成功。
- 本地独立干净检出、构建及安装同一 D，94 checks / 292 commands 全部 PASS；
  wheel metadata 和验收报告绑定准确 D。未改变现场安装。
- 保留源核验包含 17 个固定输入、20 份旧核心原件、55 份旧维护原件和既有 30 件 VM
  激活返回，未新增现场查询。原 19/7/7、Q1、运行时绑定和所有数据/进程保护保留。
- 两份调用器及独立维护验收器已冻结；合成调用器检查验证预检失败、执行失败、成功及
  重放拒绝，条件核心检查验证不完整维护状态在准备核心包之前被拒绝。

前两个候选的 CI 失败均保留，不以重跑覆盖：`b7fa374` 的 Windows 测试提前导入 Linux
模块；`951d346` 的既有 Windows 合成进程树测试返回终止未确认。具体修正见
[实现记录](Q2_CORE_HOST_FD_IMPLEMENTATION_REVIEW_20261009.md)。最终候选用自己的首次 CI 验证。

完整保留源/合成形状核算如下，均为发行前离线证据，不能代替现场成功：

| 对象 | 字节数 | 原上限 |
| --- | ---: | ---: |
| 新 marker 完整形状 | 54796 | 65536 |
| 成功 receipt 保守形状 | 41860 | 65536 |
| pre / post 描述 | 28470 / 48655 | 各 65536 |
| pre / post 压缩 bundle | 33693 / 37116 | 各 49152 |
| pre / post 展开 bundle | 143770 / 165929 | 各 393216 |
| pre / post argv | 47224 / 51788 | 各 65536 |
| 核心 transition（含真实旧原件 metadata） | 42525 | 65536 |
| approved-input 合成完整信封 | 422532 | 1048576 |
| 核心包保守上界 | 19468443 | 33550320 |

真实隔离 128-FD 合成测试覆盖交接及完整输出生命周期。维护交接峰值保守上界 127，
交接后父进程含余量 88，child 上界 64；核心准备另行核算为 124/128。
同窗 CPU/RSS、child 退出、64 CHECK 和 2 MiB IPC 上限保持。
十二代维护加原核心的 15616 MiB / 4456 inodes 义务保持，不退款。

不可变私有 freeze SHA-256：
`59a6b3d49509892bafa1dd3427406d31fd36b73a2de744b54bc4e3edaeaaddfd`。
FD1 完成；该事实不代表 FD2 或核心通过。

## 唯一 FD2 调用返回

冻结调用器只启动一次。本地 preflight 顶层退出为 3，返回：

| 字段 | 实际返回 |
| --- | --- |
| state | `BLOCKED` |
| reason | `GROWTH_USAGE_UNKNOWN` |
| error_type | `ObservationError` |
| errno | `null` |
| diagnostic | 空对象 |
| marker_created | `false` |
| ssh_requests | `0` |

预检失败后，调用器没有进入 execute。没有发出关机 token、备份、journal 镜像/文件系统
增长、维护重启或核心包；FD3/H01/Q4/H11 全部 NOT_RUN。
**09c 维护消费标记未创建**，不能写成第十二代已消费维护；十一代旧窗口仍全部消费并保留。
本次预检调用已使用，零 SSH / 无消费标记不构成重放或新窗口许可。

按准确来源，`GROWTH_USAGE_UNKNOWN` 表示宿主管理资源采样未能完整确认一个已知的
非 VM 控制子进程。返回没有保留具体 PID、失败读取字段或底层异常，不能把它归因于
某个命令、退出竞态、FD 缺额或资源超限。已有 `management_usage` 是最后一次有效样本，
不是失败样本；不能用其数值证明失败时的计量完整，也不能用零替代缺失数据。

私有调用器标记、原始 preflight stdout/stderr、实际调用器退出摘要及 stdout/stderr
均完整保留并固定大小/哈希。没有现场维护五原件或新维护索引可发布。
release gate 已转为 `FD2_PREFLIGHT_FAILED_FD3_NOT_RUN`，同时保留原不可变 freeze。

最终状态：**FD1 COMPLETE；FD2 PREFLIGHT_FAILED / STOP_AND_RETAIN；
FD3/H01/Q4/H11 NOT_RUN。** 不重放任一调用器、不放宽计量/保护、不追加现场读取、重试、
清理、恢复或新窗口。只可依据既有返回和源码做离线审阅，不能追认缺失的现场事实。

## 空诊断的源码修复

已从准确来源确认：`management_usage()` 对普通活跃控制子进程依次读取 `status`、解析
`VmRSS`、读取 CPU `stat`。原代码捕获 `OSError/ValueError/RuntimeError` 后丢弃异常；
若原有第二次 `poll()` 仍未确认退出，只留下 `complete=False`，最终返回没有诊断的
`GROWTH_USAGE_UNKNOWN`。这能解释空诊断，不能确定本次现场的 PID 或具体失败读取。

针对性修改只把已有观察保留到 `error.diagnostic`：最多八项失败子进程的 PID、已有
argv 摘要与 starttime、`status_read/rss_parse/cpu_stat` 阶段、异常类型、errno 和固定格式
原因码。不输出 argv、原始 proc 内容、异常自由文本或路径，不追加进程读取。
读取顺序、第二次退出确认、已回收 CPU 差值、资源上限、预算错误优先级、未知即拒绝
保持不变；失败样本不覆盖 `Usage.last`。缺失的已有身份字段明确为 `null`。

新增合成回归覆盖三类失败、退出分支、八子进程界限、诊断脱敏、无额外读取和原始 JSON
返回通路。既有普通用户持有进程测试必须在非 root 环境验证；不能为适应云端 root 容器
放宽 `GROWTH_CUSTODY_ORDINARY_OWNER`。源码诊断修复不代表现场故障已排除或核心通过。

本地新增 20 项诊断测试全部通过；与六个相关测试文件联合运行为 209 passed / 2 skipped，
编译与差异检查通过。另一次运行的既有 retained-custody 测试在云端 root 容器中 7 项通过、
12 项被原普通用户身份条件拒绝；未修改该条件，该组仍由非 root CI 验证。

本地接续只围绕该核心阻塞：先核对已保留的原始返回和私有调用器，确认它保留完整
`error.diagnostic`，并把修复接入新候选的离线验证。不得修改或重放原冻结调用器。
如果既有原件没有失败 PID/字段，应明确仍未知，不能用推测替代；任何后续现场执行继续
遵守原有授权范围。维护确实完成后才进入原 H01→Q4→H11，不增加旁支功能。

## 本地接续核验

本地已快进同步诊断修复 `957b300fd710cbbcff6f56b14a2739ba904ed862`，在普通用户环境
运行八个相关测试文件，**186 passed**，包括 retained-custody 的真实隔离 fork/FD 测试。
未放宽普通用户、未知资源拒绝或原资源上限。

私有离线检查进一步把新源码实际产生的三种 `status_read/rss_parse/cpu_stat` 失败，
经过顶层 JSON 输出，再接入原冻结调用器的合成 subprocess 返回：原始 stdout、保存的
摘要和打印的摘要均完整保留同一诊断。每种情况只模拟一次 preflight 返回，不进入 execute；
所有启动均被测试替身拦截，无真实命令启动、SSH 或现场窗口。原调用器无需修改。
五个冻结脚本与原 freeze 哈希一致，六份已保留返回与原索引一致，终态 gate 不变。
合成结果单独保存，没有替换历史原件或补写缺失的失败 PID。

准确修复提交的 13 份来源、17 个固定输入、55 份旧维护原件及既有 VM 激活材料离线
核验通过。宿主协调器为 97012 B，仍低于 98304 B；pre/post bundle、argv、描述、marker
的保留源形状与本记录原核算一致，均在原上限内。这不是当前现场准入或新 freeze。
首次沙箱内固定源读取被父目录保护检查拒绝；保留该离线失败记录后，在普通用户原生
文件系统视图下通过同一核验，未修改任何目录保护条件。

截至 2026-10-10 00:50（Asia/Shanghai），修复的
[首次 push CI 37960982460](https://github.com/kongbu0621/infra-local-hand/actions/runs/37960982460)
为 attempt 1：classify-change 与 Windows 已成功，Linux 尚在运行，不能记为 3/3。
本次无现场操作；FD2 仍为 PREFLIGHT_FAILED / STOP_AND_RETAIN，FD3/H01/Q4/H11 仍为 NOT_RUN。

## 控制子进程正常退出时的计量修复

诊断修复 `957b300` 的首次 CI 后续已完成，结论为 success。Owner 随后要求本地直接
修复核心阻塞。隔离的自建普通 Python 子进程在正常释放内存并退出时，首次合成案例
复现 `stat/status` 分开采样路径中的 `status_read / GROWTH_PROC_DRIFT`，外层返回
`GROWTH_USAGE_UNKNOWN`。这证明存在一个正常退出计量缺陷；原 FD2 没有诊断，仍不能
将这次合成原因追认为历史现场原因。复现未读取现场对象或执行 SSH。

普通控制子进程现在用原有有界 proc reader 读取一份 ≤4096 B 的 `stat`，从同一记录
取得启动时间、CPU ticks 和 RSS pages，核对其已创建且未回收的 Popen PID/start 绑定。
初始快速启动读取未取得 start 时，只允许绑定这次完整记录的有效 start，不增加观察。
格式缺失、负数、未知状态、PID/start 不符仍停止；身份不符不能被随后退出掩盖。
RSS 为零只接受内核完整数值字段，不把缺失数值或读取失败替换为零。

[内核 proc 文档](https://docs.kernel.org/filesystems/proc.html)说明 stat 中的 CPU/RSS
字段；[内核实现](https://github.com/torvalds/linux/blob/master/fs/proc/array.c)在 mm
已释放时省略 status 的内存段，而 stat 仍输出数值 RSS。这个变化避免对已知短命
控制子进程套用稳定文件的 uid/gid 元数据比较；使用原 CPU 读取路径已有的 no-follow、
大小和 EOF 检查，并增加数值与 PID/start 绑定。业务进程/写入者检查、保留原件保护、
常驻 custodian 的提前退出拒绝及所有限额均保持。没有增加等待、补读、重试或扫描。

九个相关文件 **209 passed**。新增回归覆盖原限额下真实子进程完整退出、单记录计量、
明确零值、缺字段/负值/错 PID/start 拒绝、退出后的身份矛盾，以及已有诊断返回通路。
真实生命周期 fixture 固定八个独立案例；首次测试因合成采样次数上界不足而失败，
仅调整该测试自身的有限循环上界，生产限额未改，失败日志保留。宿主源码仍小于原
98304 B 上限。准确提交的 CI 和独立安装结果另行记录，不能用本地通过提前代替。

本节为 FD1 既有资源计量要求内的普通修复，不增加执行许可。旧冻结脚本、终态返回和
消费记录未改；FD2 仍停止，H01/Q4/H11 仍未运行。
