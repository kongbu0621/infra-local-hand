# 已修复 VM 接入：实现与验证

本实现承接独立 C `31b8e21116edd3678d738c1b9525edb6b3da8ae8`，
范围为准确 A `13cd2d3e7ac9a307a7c960f713524fefa2959a95` 的 VA1–VA3。
A 三文档原字节不变。Owner 的整批批准见[决定](../governance/Q2_CORE_VM_ADOPTION_CONTINUATION_OWNER_DECISION.md)。

## 行为与边界

维护入口从已保留的 30 份准确启动/安装返回接入当前 VM，核对批准、冻结 helper、
原始 PID/start/argv、host/guest boot、活动镜像及准确包安装/quota 返回。核心端独立
校验历史 boot、当前 boot 与维护后 boot 的关系。启动前镜像摘要保留为历史候选证据，
运行期间正常写入不再错误地与启动前内容比较；路径、inode、权限、进程身份和关机后
稳定性保护保持。活动 system 的路径仅从私有冻结输入取值，不写入公共源码。

加入九代准确旧维护原件和十代完整费用。仅 marker 顶层重复 resume 改为 SHA-256
引用；完整历史仍在 manifest、receipt、transition 和核心输入中，原 65536 B 上限不变。
新维护为 `lhqjgrow-20261009a`，manifest/receipt v11、preflight v10、transition v10。
旧08f仍按它原来的 v10/v3解析。新 guest report/input 继续 v3；进程/writer拒绝不变。

主机与独立核心消费者绑定准确 A/B/C，发布允许表只接受本实现的 dispatcher 字节。
私有新调用器接入同一 activation archive，完整保存失败诊断；旧调用器不得重放。
准确 D 发布、首次 CI、独立安装、原件/包上限检查及双调用器冻结全部完成后，
才允许 VA2。只有维护原件全部成功验证后才允许 VA3。

## 验证范围

候选离线回归 2943 passed / 35 skipped。绑定准确闭合记录后发现合成 Git 仓库未登记
VM_ADOPTION，产生 8 个测试失败；补齐合成 A/B/C 后，冻结与接入相关 124 项通过。
最终完整相关回归 **2979 passed / 35 skipped**（71.95秒）。30份真实既有启动返回与固定 archive 通过
新验证器，零现场采集。旧08f五件重新逐字节与原私有索引交叉核对后披露如下。

测试与离线投影不代表现场成功。此实现提交时尚无新维护动作；H01/Q4/H11 NOT_RUN。
九旧失败/UNKNOWN和所有旧记录保持，不推断旧08f的匹配进程或字段。

## Owner 允许公开的旧08f最小索引

准确旧 D `db6e7165322da3072ca1fd88a36401e18ebd4a86`。仅下列 basename、bytes、
SHA-256 公开；原始内容、启动返回索引及新09a索引仍私有。

| basename | bytes | SHA-256 |
| --- | ---: | --- |
| .lhqjgrow-20261008f.consumed.json | 64566 | 75e0e745f13745d3efd45d52495d13bd8ea5a3ff626316fbf5168a5a493e30af |
| .lhqjgrow-20261008f.events.jsonl | 441 | 264edd9660fd59ba3b6884ae4df0cdd8846a16a4cc97665a835f5fa691d91749 |
| .lhqjgrow-20261008f.pre.stderr | 817 | df134297b8556f6d3939fe17424807a44e275c57470c84d81577d1da30d307b8 |
| .lhqjgrow-20261008f.pre.stdout | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| .lhqjgrow-20261008f.receipt.json | 15447 | de08569fc6fadccafcf434d842e43ad713fbb4b6fdb7c45d03cf95df5fa3ad4e |

## 09a 返回后的普通修复与离线接线复核

09a 已消费失败，详见[现场记录](Q2_CORE_VM_ADOPTION_FIELD_20261009.md)。保留返回只说明
用户管理器 show 上下文发生 errno 2，不能识别缺失路径或具体步骤。本复核没有新 SSH、
VM 查询、服务动作或维护窗口；原返回和冻结字节不变。

已修复独立核心消费者的路径表示错误：历史 systemd `ControlGroup` 为逻辑路径，
采集端用 `/sys/fs/cgroup` 加该路径并返回完整文件系统路径；原消费者直接比较两者，
会拒绝正确结果。现在使用采集端相同的前缀转换，然后仍要求完整路径精确相等。
未修改历史 locator 来源、目标、管理器、权限、cgroup 内容或资源限额。
对应 dispatcher 发行摘要同步；发行仍受完整维护成功等原条件限制，不能重放旧 caller。

新增回归在修复前得到 **1 failed / 8 passed**，失败为真实逻辑路径表示触发
`CORE_DISPATCH_ADMISSION_CGROUP_BINDING`。修复后相关 admission、capacity、dispatcher、
entry、freezer 回归 **526 passed / 10 skipped**。覆盖逻辑/完整两种输入表示、错误管理器、
重复前缀及缺失挂载前缀拒绝。测试不代表现场验收。

复核还确认两个不能用上述普通修复替代的生命周期/来源问题：

1. 固定候选 `4b6e4a7c403362358192086b88679e1326dcb2e1` 的准备程序在当次启动
   UID 1100 用户管理器，并把用户 slice 配置写入 `/run`；未开启 linger。VA1 只接入
   VM/boot 身份，没有补充重启后的运行时准备。原维护 pre/post 都需要该用户 bus。
   这是源码可证的准备缺口，不是对本次具体缺失路径的现场断言。
2. 已校验原始 locator 来源中，`ordinary_parent_unit` 与保留用户 slice basename 相同。
   当前 collector 将两个角色均交给 system manager 并按 unit 名去重，而 geometry 又要求
   ordinary 为 32 tasks、retained ordinary 为 64 tasks，同一条记录不可能同时满足。
   已固定的 20261001e 系统准备 plan 指定了不同的 system ordinary slice（32 tasks）及
   原 retained user slice（64 tasks）。该计划是历史计划，不能据此断言它已经在现场创建。

原 plan/retry 取自既有 collection 的精确归档成员；系统 plan 取自
`q2_core_obligation_inputs.DELTA_PINS` 的 `plan`，30813 B，SHA-256
`85633b837718282ba6590b7a6679d51aa60addfb0f5be39ea929af83de4a45c1`。
归档摘要与成员摘要均已核对；原件、解析投影及机器目标名仅私有保存。

修复后续接线需准确区分历史 locator 与当前 system/user 角色，并在维护两侧准备原目标
运行时配置。VA1 方案曾明确 guest 仅更换 session；新增启动/创建动作及新窗口不能借用
消费完的 VA2。先准备合并的最小变更方案，再由 Owner 对这一完整批次决定；不逐步骤
申请诊断窗口，不跳过 bus 或把域检查改成缺席即通过。H01/Q4/H11 仍 NOT_RUN。
