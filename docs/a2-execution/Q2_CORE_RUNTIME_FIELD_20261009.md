# RT1 冻结与 RT2 原始返回

范围 `LH-Q2-CORE-RUNTIME-CONTINUATION-v1`。准确 A/B/C
见[基线](../governance/Q2_CORE_RUNTIME_CONTINUATION_BASELINE.md)，实现见
[复核](Q2_CORE_RUNTIME_IMPLEMENTATION_REVIEW_20261009.md)。本记录不更改 A 或冻结 D。

## 准确候选与冻结

- 独立 C：`3633b1e963b35647bef8d7f94592089130ff25a1`。
- 直接实现子提交 D：`547bbb05816e17525470b1a3c136b328ff96adc1`，tree
  `d837ab5f94bb7fec72abea1d1fa6691f63f33e08`，已发布 main。
- [首次 CI 37938662213](https://github.com/kongbu0621/infra-local-hand/actions/runs/37938662213)
  attempt 1：三项成功。Linux 7267 passed/89 skipped；两平台独立安装步骤成功。
  本地独立安装验收同 D：94 checks/292 commands 全部通过。
- 固定 50 件旧维护原件及原来源闭合核对通过。准确 D 的 pre 静态标记形状 63877 B；
  合成 transition 23569 B、approved-input 402422 B，完整核心包上界 19463512 B，
  均低于原上限。合成数据仅用于离线验证，实际核心包未构建。
- 维护及条件核心 caller 均已冻结。私有不可变冻结摘要
  `0af7c61e7890f09331c7a8097ca5d228fc91c499420234557393b8aa298ffb1b`。
  模拟链验证成功、失败和重放拒绝；条件核心在维护未验证时阻止准备和发行。

## 唯一 RT2 的实际结果

`lhqjgrow-20261009b` 本地预检通过，同窗 execute 创建消费标记后返回
`STOP_AND_RETAIN / LOCAL_IO_OR_TRANSPORT`，`OSError errno 24`（打开文件过多）。
started 仅有 `CONSUMED` 和进入 `GUEST_QUIET` 的尝试记录，不代表 guest 已静止。

receipt 的 `ssh_requests=1` 在 transport 构造前递增；`transports=[]`，原 pre.stdout
和 pre.stderr 均为空。因此只有一次请求尝试的记录，不能宣称 SSH 已成功启动或 guest
执行过准备。原始返回不能区分具体哪次 FD 分配失败，remote_exit 保持 UNKNOWN。

原事件没有 poweroff token；没有进入备份、镜像增长、VM 重启或文件系统增长。
没有 guest 报告，不能从空输出推定其动作结果。RT2 CONSUMED_FAILED，
RT3/H01/Q4/H11 NOT_RUN，实际核心包未生成或发出。

五件原始返回已保护读取、核对并私有留存。由于没有 transport 记录，空流不能声称
已与不存在的 transport 摘要交叉验证。新索引保持私有；原不可变冻结单独保留，
发行门已登记终态 `RT2_CONSUMED_FAILED_RT3_NOT_RUN`。没有重放或补充现场查询。

## 离线 FD 成本复核

从准确 D 和既有输入集合即可确认宿主设计超过 128，无需再观察 VM 或宿主进程：

| 持有类别 | FD 下界 |
| --- | ---: |
| 固定输入（含 activation 归档） | 17 |
| 管理锚目录、六件管理文件、两个工具 | 9 |
| 原核心及诊断返回 | 24 |
| 原容量返回 | 4 |
| 十代旧维护原件 | 50 |
| QEMU 与镜像工具 | 2 |
| 五个镜像及已采用 system 父目录 | 6 |
| 当前 VM 的 pidfd | 1 |
| 标准输入/输出/错误 | 3 |
| 合计（创建新输出前） | 116 |

消费标记及事件文件加 2，pre 两路保存文件加 2，提前建立的 selector 加 1，
成为 121。Python fork/exec 的三组管道及错误管道临时再需 8，峰值下界为 129。
这解释了为何普通预检能够通过，而带双向 stdin 的传输创建会触及 FD 上限；
不据此虚构本次具体失败 syscall。后续阶段还有新增输出，不能只删去一个临时 FD
便宣称整条维护路径满足限制。

先前 98/128 的离线证明只覆盖 guest，漏掉宿主峰值，这是本次验证缺口。
现有材料不足以证明另一种 FD 生命周期安排等价保留所有旧身份保护；不擅自提高上限、
关闭保护 FD 或删减历史义务。十一代消费、所有旧 UNKNOWN 和完整费用继续保留。
本次批准已停止，任何进一步现场执行必须先完成足够的离线修复与必要授权。
