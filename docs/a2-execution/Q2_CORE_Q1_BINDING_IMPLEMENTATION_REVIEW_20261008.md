# QI1 来源接线与候选验证

本记录对应 `LH-Q2-CORE-Q1-BINDING-CONTINUATION-v1`。准确 A 为
`e66b1b5524f22d60c810dffac59ca418c5ad4236`；Owner 原文保留在
[决定 B](../governance/Q2_CORE_Q1_BINDING_CONTINUATION_OWNER_DECISION.md)。独立 C 为
`61fae1da528105605a023f260130c4e0d9c1bc02`，本实现直接承接 C，未合并关闭记账与实现。
三份 A 文档未改，R 不变。

实现从已保留的 C10、原单单元请求和返回索引重算唯一 Q1 服务及父 slice。
保留原配置配对、票据规范编码、七项名称身份、同配置 source/boot/parent 关联；
旧清单重建后仅由 18/6/6 增为 19/7/7，服务 cgroup 非 null。
新来源使用既有受保护 reader，并在预检与消费前复核同 FD、名称、元数据及字节。
核心原件消费者再次重算相同声明，不以摘要外壳替代来源验证。

维护与独立核心消费者均接入第七代 08d 历史，按其原 v8 manifest/receipt、v2
guest 报告、六代嵌套 resume 和原 assurance 验证失败。35 原件、28 缺席名和八代
维护费用全部保留。协议版本及新 08e session 同步到 host、freezer、approved inputs、
dispatcher 和 entry；原 loader、bootstrap、runtime、wheel 和现场安装不变。
GuestInventory 除 session 外没有变化，全部实际 quiet、启动边、cgroup、writer 和
数据检查继续执行。[旧08d最小索引](Q2_CORE_GUEST_STARTUP_ORIGINALS_INDEX_20261008.md)
按本次披露批准发布；其他原始内容仍私有。

## 已完成的离线核对

- 八个固定来源角色与既存私有来源索引相符；七个被该索引覆盖的原件身份、字节、
  mtime/ctime/atime 一致。08d stderr 另由准确五件索引绑定。没有恢复元数据。
- 16 个静态输入角色、20 件原核心失败原件、4 件诊断、4 件容量原件及35件旧维护
  原件均通过现有关系核验。没有新增 SSH、VM 观察或维护 marker。
- 使用真实保留输入和当前待提交源码计算：descriptor 26337 B、压缩 bundle
  39890 B、展开 bundle 137104 B、远端 argv 55315 B、静态 marker 形状 61049 B。
  均在原上限内；这些不是当前 VM 状态或实际维护结果。
- 受影响的核心/维护回归：3204 项通过、48 项跳过；唯一剩余失败是测试进程
  umask 077 导致旧 fixture 的目录模式与其 0755 断言不符。使用 CI 的 umask 022
  单独复核该用例通过，合计3205项通过。跳过不计为通过。
- 更早本地结果保留：新增代码缩进错误、旧 fixture/版本/费用常量遗漏已修正；
  沙箱禁止私有 D-Bus socket 和真实父目录元数据时的失败未转记为通过。
  后续隔离回归使用真实普通身份和临时 fixture，未访问 guest。

新增合成验证覆盖来源 pin/配置/票据错配、重复或冲突声明、FD 与命名对象变化、
历史 v2/assurance/resume 混用、来源或清单被篡改时禁止核心输入，以及维护成功后的
双消费者验证。合成成功不能代替 QI2/QI3 现场验收。

## 本提交时的剩余步骤

准确提交 D 的 CI、独立安装、完整核心输入大小核对和两 caller 冻结尚待完成；
QI2 NOT_STARTED，QI3 NOT_RUN。全部完成后才允许一次 `lhqjgrow-20261008e`，仅在
原维护完整 VERIFIED 后接 `lhqcore-20261007a` 的 H01→Q4→H11。
失败即停止；全部旧窗口继续消耗，不重试、补采、清理或扩展。
