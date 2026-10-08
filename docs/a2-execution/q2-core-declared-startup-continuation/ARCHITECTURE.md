# 只核对声明目标，完成原维护与核心接续

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-DECLARED-STARTUP-CONTINUATION-v1`，仅 DS1–DS3，依
[需求](REQUIREMENTS.md)及[实施计划](IMPLEMENTATION_PLAN.md)。
输入基线 `b4dde5d387a9206a41925a2d051b51eb74fb0235`，准确 QI 实现 D
`fa30146b0a49744b25df0f23969bf96b17eaacad`。沿用根 AGENTS 固定 R、Owner authority、
来源完整性及 R→A→Owner B→独立 C→D；本文件自身不关闭 Gate。

## 一次缩减维护启动覆盖

08e 已在实际 19/7/7 清单上遇到另一未声明服务；现有原件只证明其 ExecStart 命中
保护根，不能证明它当前活动，也不能补成已批准的 Q1 唯一声明。此次不再逐个收集
历史服务身份，不新增白名单、扫描器、模板解释器或现场补查。

删除 guest 维护的全单元启动枚举：不再调用 `list-units`、`list-unit-files` 或模板
`cat`，也不再根据这些未执行的读取声称已核查所有直接或间接启动入口。维护只核对
准确冻结的声明目标，并保留当前进程/writer 与数据保护。未知单元及模板的直接引用
检查不再执行，这是保证范围缩减，不是等价修复；未发现冲突不代表完整启动清单。

管理依据仍为 Owner 明确接受、执行者在既有交接中确认的可信单管理员前提：维护
开始、停机前、原配置重启后的 post 阶段直到原核心交接，不从未声明入口自动启动
旧业务，不新增这种入口，也不从其它会话手动启动旧业务或写受保护目录。它不是
观测结果；不能确认或存在实际相反证据即停止。一个残留的服务定义本身不等于
该前提已违反，实际业务进程或 writer 仍由原检查拒绝。

## 保留原来源及准确清单

`freeze_growth_inputs` 继续从原受保护输入、既有私有索引和 QI 来源组重建全部
source binding。C10/C11 pins、捕获原件关系、原 Q1 七字段名称计算、同配置父域、
来源/boot 关联和固定 18/6/6→19/7/7 合并全部保持。C10 不是完整 Manifest、当前
cgroup 或持续静止证明；原 false 覆盖字段保持。此次不采用第二个服务来源，不新增
或删除 expected_units、domain_units、domain_cgroups、protected_roots、essential_paths。

Q1 采用事实继续绑定原 QI 授权，当前 DS 授权只覆盖本次保证调整和接续；不能将
新授权替换进旧来源记录，或以一份外部修改后的 inventory 字典代替重建。
O_NOFOLLOW/O_NOATIME、权限、普通文件、长度/摘要、跨角色 inode 去重、held FD
及命名对象复核沿用。原件及准确私有路径不公开，不回 guest 补证。

## GuestInventory 仅查询声明域

`collect()` 原有顺序和两次核对保持：expected_units 的 `quiet_service` →
domain_cgroups → 声明域检查 → `processes()` → `persistent()` → 同一 domain_cgroups
及 expected_units 再核对。原单位身份、静止状态、Restart、启动依赖、Job、预期
control_group、cgroup.events/procs、重复观察一致性不改。expected 服务只由这两次
既有检查负责，不再在 startup 报告中复制一套 `related` 服务检查。

`startup_manager` 按 system/user manager 选择原 `domain_units`，按名字确定顺序，
仅使用现有 `show_many` 查询这些准确名称；没有该 manager 的域时不发空查询。
保留原 30 项响应解析、别名/重复标量/Exec 多值规则和 systemctl 返回、EOF、stderr、
工具身份及 UID 1100 bus/account 约束。逐域仍要求：准确 Id；LoadState 为 loaded
或 not-found；ControlGroup 为空或等于声明值；名称为 slice；所有 Exec 属性为空。
不查询这些属性提到的其它单元，不改服务、配置或 systemd 状态。

新 guest input/report 为 v3。`quiescence.startup` 始终含 system；仅当声明存在
user 域时含 user_1100，不能出现其它 manager。每个 manager 的准确字段为：

```json
{
  "scope": "DECLARED_ONLY",
  "domains": [],
  "undeclared_unit_inventory": "NOT_PERFORMED",
  "indirect_startup": "NOT_PERFORMED"
}
```

上例空数组只表示字段形状；真实 `domains` 必须逐项等于该 manager 的声明域名称
集合，保持原每行 `{name, properties_sha256}` 形状。验证者检查准确字段、字符串
名称、有效摘要、无重复、按名称排序、没有遗漏或多余名称；system 没有声明域时才
允许其空数组。不能沿用原仅检查 list 类型的宽松覆盖验证。移除 `unit_count`、
`related`，不填零伪装全量盘点。属性摘要表示实际已声明域的观察，不代表未查单元。

## 覆盖对象贯穿生产者和消费者

`guest_startup_assurance` 为准确五字段，新增字段只描述未声明单元的覆盖：

```json
{
  "mode": "TRUSTED_SINGLE_ADMIN",
  "indirect_startup_observation": "NOT_PERFORMED",
  "undeclared_unit_inventory_observation": "NOT_PERFORMED",
  "no_undeclared_business_startup": true,
  "continuous_exclusion_proven": false
}
```

它不表示声明域、声明服务、当前进程或 writer 检查被删除。未知字段、缺字段、
类型混淆及不相等值一律拒绝。沿原通路绑定 frozen/source_binding、manifest、marker、
receipt、pre/post descriptor/report、POWER_OFF_REQUESTED、失败返回及核心 transition；
两端不能只验外壳摘要而接受旧覆盖对象。host 的 writer_observation=NOT_PERFORMED、
access_mode 与 continuous_exclusion_proven=false 保持原语义，不合并为 guest 覆盖。

现有 `processes()` 的完整性、数量、FD、maps、身份/复用/漂移、业务路径及 writable
检查全部保持，不因扫描到无关进程而另放宽。持久目录检查、五池身份、journal 树与
内容比较、设备 serial/UUID/大小、resize2fs 工具身份、QEMU pidfd/start/executable/
完整 argv、五镜像保护、正常关机及旧 pidfd 退出、qemu-img 锁、完整独立备份和比较、
一次原配置启动、ext4/容量核对及所有原时限/资源限额均不变。

## 新旧记录严格区分

新维护 session 固定 `lhqjgrow-20261008f`；manifest/receipt v10、短预检 v9、
guest input/report v3、journal-transition v9、historical-capacity-obligations 和
reconciliation v13、host-capacity-condition v12。版本调整只绑定此次准确语义，
原任务 H01/Q4/H11 合同不变。短预检继续只携完整 resume 摘要，不扩大 4096 B。

历史按 06a→07a→07b→08a→08b→08c→08d→08e 八代保留；08e 使用准确 QI
A `e66b1b5524f22d60c810dffac59ca418c5ad4236`、C
`61fae1da528105605a023f260130c4e0d9c1bc02`、D
`fa30146b0a49744b25df0f23969bf96b17eaacad`，manifest/receipt v9、guest input/report v2。
08e 五原件及其已保留私有索引必须先核对，pins 不得由任意当前文件重新自洽生成。
公开最小索引只按本需求的明确披露范围处理；当前新窗口原始流及索引仍私有。

历史解析显式区分：前六代 guest v1；08d、08e guest v2 并使用准确旧四字段
assurance。08e 的嵌套 resume 必须仍是其原 QI 七旧历史，08d 仍是其原 GS 六旧历史。
新五字段验证器不能回套旧记录，不补新字段、不改旧原字节、消费、失败或 UNKNOWN。
加入 08e 时不能沿用旧 `version == 8` 才接受 guest v2 的分支而误判 v9。

预检、消费前同 FD 复核及核心读取共同覆盖 40 件旧维护原件、32 个旧后续缺席名和
新九名 create-only 对象；新增 08e profile 仍是动作空、一次 SSH、PRE_QUIESCENCE /
GROWTH_UNDECLARED_BUSINESS_UNIT、remote_exit UNKNOWN，其它旧 profile 保留各自原阶段和原因。
声明补齐不改变 08e 失败事实。
九代维护各 1296 MiB/370 inodes/120 nominal CPU-s，合计 11664 MiB/3330 inodes/
1080 nominal CPU-s；加原核心 capture 为 11728 MiB/3346 inodes。旧实际用量与未知
义务不退款，不按小失败文件释放预算。

## 先完成两侧，再发一次维护和条件核心

DS1 一次完成维护 producer、`build_journal_transition`、core contract/freezer/
approved-input/package/entry、独立 dispatcher/bootstrap 和返回验证者的接线。
host 从同一受保护来源重建 inventory/Q1 proof，校验全部 pre/post、覆盖、状态链、
源摘要、原件和容量/boot 关系；独立 guest 校验 host 已核验投影，不声称重读私有 C10。
当前 transition 的五字段覆盖验证及独立消费者同步；离线 Windows 投影路径继续
使用纯数据校验，不引入 Linux runtime 模块。dispatcher pin 从准确候选字节更新。

发布、准确 D CI、独立安装及真实保留输入核对后，先冻结维护和条件核心两个 caller。
实际 descriptor、marker、短预检、transition、approved-input、源码和 bundle 都按
原上限核查，特别保留 marker 65536 B；不能因新增一代历史提高任何上限或截断历史。
合成成功只验证消费者与大小，不能成为现场成功或提前生成真实核心包的依据。

DS2 沿一个新原点/nonce/manifest/累计计量执行唯一 08f 维护，原最多两个固定 SSH
阶段和状态机保持；失败 STOP_AND_RETAIN。只有完整成功原件通过核验，DS3 才构造并
发出同一 D 的原未发行 `lhqcore-20261007a`，依次 H01→Q4→H11。旧 caller 和已消费
窗口不得重放；不重试、补采、清理、恢复、回滚或二次启动，不自动追加下一维护窗口。
这个覆盖调整消除全单元穷举依赖，不保证其它保留的实际准入必然通过。
