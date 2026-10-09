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
