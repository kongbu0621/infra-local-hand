# 完成收窄检查与原核心接续

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-DECLARED-STARTUP-CONTINUATION-v1`，DS1–DS3。
以 `b4dde5d387a9206a41925a2d051b51eb74fb0235` 为事实输入，依本目录
[需求](REQUIREMENTS.md)和[架构](ARCHITECTURE.md)。本提案不执行源码或现场动作。

## DS1：完整实现、验证与冻结

1. 三文档形成准确 A；Owner 接受覆盖缩减、管理前提、DS1–DS3 和限定披露后，
   保存真实 B，独立 C 只作关闭登记，D 承接 C。旧批准不自动转移，范围内不逐步审批。
2. 在 `q2_journal_growth_guest.py` 将 startup_manager 收窄为声明域的原属性核对，
   去掉 list-units/list-unit-files、未知单元解析及模板 cat 路径。保持 show_many 的
   严格语义和全部声明域属性检查，返回明确 DECLARED_ONLY 记录。collect 中两次
   quiet_service/cgroup 以及 processes/persistent 检查原样保留；不借本次修改
   `/proc` 竞态处理、PID/FD 检查、凭据、权限或任务执行器。
3. 在原 assurance 中增加准确范围字段，更新 guest descriptor/report v3、
   manifest/receipt v10、preflight v9、transition v9。host 与独立 guest 严格核对
   新五字段对象和新的 startup 结果结构，不为缺字段默认补值，不继续报告全量扫描。
   新 session 固定 08f，旧 Q1 来源变换、19/7/7 清单和所有旧 pin 保持。
4. `q2_core_prior_attempt.py` 增加第八个 08e 失败 profile，原 D fa30146，按 QI 的
   manifest/receipt v9、guest v2、原四字段 assurance、七代嵌套 resume 验证。
   历史验证与新保证分开，不用当前五字段验证器拒绝旧原件，也不把旧字段升级。
   从原私有索引与原件一致核对固定 08e 五件 pins，保留原失败、消费和 UNKNOWN。
5. `q2_journal_growth.py`、core contract/freezer/approved-input、package/entry、
   独立 dispatcher/bootstrap 和返回消费者同步新 R/A/C/D、八旧历史与九代费用；
   reconciliation/history v13、host-capacity v12。更新实际改变的 source digest，
   保留未变 loader/runtime/wheel 和所有历史 pin。旧 40 件、32 缺席名、新九名及
   原件保护读取、跨集合 inode 去重、同 FD 消费前复核保持。
6. 本地保护读取已留存真实输入，离线完成两侧构造/解析、来源和大小核对。无需新
   SSH、再次查新服务、寻找 C10 或诊断采集。准确 D 发布后核对其 CI 和独立安装
   验证，现场安装保持；所有条件满足才冻结同一 D 的维护及条件核心 caller。

只围绕本次改变验证真实风险：

| 验证点 | 要求 |
| --- | --- |
| 查询范围 | pre/post 均不发 list-units、list-unit-files、template cat 或未知 unit 查询；仅访问声明目标/域及原保护对象 |
| 正确覆盖声明 | DECLARED_ONLY 与 NOT_PERFORMED 绑定到准确五字段 assurance、source/manifest/transition；旧 schema、缺字段/错类型/多字段和虚报全量扫描拒绝 |
| 已知目标保护 | 声明服务活动/有启动边、cgroup 非空/身份变化、域 Id/path/Exec 不符、当前业务进程/FD/mmap writer 和持久证据异常仍拒绝 |
| 管理前提 | 未确认/否认或已有相反证据时停止；不能从没有未知单元查询推导为真 |
| 历史与来源 | 08d/08e 四字段语义和旧报告版本保持；八代顺序/pins/消费/UNKNOWN/费用、Q1 来源或 inventory 改动即使重算摘要也拒绝 |
| 端到端接线 | 合成维护成功能构造并经独立消费者验证原 H01/Q4/H11 输入；任何维护不完整均不发行真实核心包 |
| 原上限 | 真实静态来源加八旧历史，最大计量和 20 位钟下，短预检、marker、transition、approved-input、包及压缩/展开 bundle 均不超原界；纯投影验证不导入 Linux runtime |

使用现有或合成隔离对象，不为测试再次访问现场。复用未改部分的有效证据，新候选仍
须有自己的 CI/独立安装验证；如实保留首次失败和环境跳过，不以重跑抹掉结果。
该批两侧完整后才进入 DS2，不把后续消费者缺项留到维护成功之后再实现。

## DS2：唯一 08f 维护

执行者确认既有 host 前提与本次明确的 guest 前提仍成立后，使用同一冻结 D 和
原连接执行普通预检及同窗 execute。沿原 900/780 秒、原点/nonce/manifest/累计
计量和最多两次固定 SSH，完成目标静止、正常关机/退出、完整备份、journal
256→512 MiB、比较、一次原配置启动、ext4/UUID/内容/容量检查，全部通过才 VERIFIED。
开始即消费，失败 STOP_AND_RETAIN；不重试、补采、清理、恢复、回滚或自动申请下一窗口。

## DS3：直接运行原三个核心 case

host 保护读取并完整验证 DS2 八件成功原件和八旧历史，使用同一来源构造新
transition，发行原 `lhqcore-20261007a`。独立 guest 验证投影、coverage、来源、
boot 与原准入后，原 live finalizer 依次执行 H01→Q4→H11；已有对象不换名重发。
保留原独立 900/800/750 秒及全部单次资源限制。交付实际 verdict；若 DS2 不完整，
DS3/H01/Q4/H11 均 NOT_RUN，不能把范围缩减或 CI 通过当作核心交付完成。
