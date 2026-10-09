# 一批完成运行时修复、维护及原核心任务

**PROPOSED / Gate OPEN / NOT APPROVED**。Scope `LH-Q2-CORE-RUNTIME-CONTINUATION-v1`，RT1–RT3。
依[需求](REQUIREMENTS.md)和[架构](ARCHITECTURE.md)；本文件不是 Owner 决定。

## RT1：完整实现并验证后冻结

1. 固定本三文档为准确A，保留真实Owner B；独立C只登记闭合、准确引用和必要脱敏索引。
   D必须继承C，不能把C/D合并或事后修改A的历史OPEN字节。ordinary路径修复有独立
   已有提交，不冒充本范围实现。未闭合前仅准备文档及只读来源复核。
2. 在现有 `q2_journal_growth.py`、guest及 `q2_core_approved_inputs.py` 的原来源读取
   中接入角色投影；采用现成精确原件，不另做采集。`q2_core_delivery_dispatcher.py`
   独立同步角色来源、查询管理器、geometry与最终验证；历史 locator 保留原语义。
3. guest pre/post 各接入一次限定准备。配置模板取准确原source，system ordinary参数
   取准确system plan；配置创建/复用、启动、验证均依架构顺序，失败停止，不能回调
   已消费retry/setup程序。只修这一条业务必需路径，不建立通用修复或诊断框架。
4. `q2_core_prior_attempt.py`及独立consumer保留十代50件旧原件，增加准确09a profile。
   完成manifest、receipt、description/report、transition、approved-input及host-capacity
   字段/版本和相同费用更新；成功pre/post真实生成端必须由host及核心消费者共同校验。
5. 检查固定历史plan/retry/system plan的role映射和模板，构造以下必要回归：
   - 真实源关系：原ordinary与retained同名仍保留历史含义，实际system ordinary从准确
     新源取值；交换源、篡改目标/限额/父域、只改producer或consumer均被拒绝。
   - 重启准备：正确已存在对象复用；两种配置缺席时只create指定对象；匹配的inactive
     目标只start一次；当前boot与post新boot均可完成顺序，第三次/同阶段重放拒绝。
   - 禁止冲突覆盖：wrong owner/mode、symlink、内容/drop-in/遮蔽、failed/job/非空域、
     tool/bus/父目录漂移、start失败或未EOF、准备后业务进程出现都停止，不继续增长。
   - system/user实际查询分离：user helper固定身份/环境、凭据不留在root执行；相同unit
     basename不能混淆两个manager；retained路径转换、32/64 tasks和geometry同时验证。
   - 报告链：以guest实际生成的pre/post报告测试host及独立consumer，缺准备记录、旧schema、
     前后boot/原件pins/投影不一致、历史09a误当新成功均拒绝。
   - 原失败/UNKNOWN和所有资源原限额不变，计量超限、包超限、缺历史文件均不发行。
6. 用保留真实输入核对固定映射、50件原件、30件activation archive、Q1来源；核对两份
   源码、压缩/展开bundle、pre/post descriptor及实际SSH argv、marker、transition、
   approved-input、完整核心包上界、新增runtime成本、FD和累计费用。不得以合成数据
   宣称当前guest已再次核验；不得为静态核对发SSH。实际原件固定摘要不自动随代码更新。
7. 相关测试通过后发布main，等准确D首次CI三项成功，并完成独立安装验收。分别冻结新
   维护caller与条件核心caller，原clock、nonce、输出上限和资源成本绑定同D。旧caller
   保留不可重放，Owner范围内无需再次询问每个子步骤。

## RT2：一次准备及维护窗口

运行09b普通预检，同窗execute消费标记后发固定pre SSH，依架构完成当前boot的运行时
准备、完整静止/数据验证和pre报告。host验证并持久保存原报告后才发poweroff token。
确认原QEMU真实退出，完整备份journal、一次镜像增长与逻辑比较、一次原配置维护启动。
固定post SSH在新boot完成第二阶段运行时准备和原quiescence，再执行一次resize2fs、
校验UUID/内容/容量/父目录，收齐报告及真实完成状态。journal须满足原400 MiB/32768 inodes。
所有步骤仍在一次900/780秒窗口内，最多两次SSH。失败留下部分动作和原始返回，不重试、
不补采、不停止额外服务、不清理、不恢复或另开窗口。

## RT3：同一任务的三个实际核心结果

保护读取RT2完整成功原件，验证来源、动作次数/顺序、数据、runtime projection和新boot。
条件满足才发行原07a包，通过原live finalizer顺序执行H01→Q4→H11，并报告各自实际verdict。
新runtime对象只提供既定父域，不变更业务case、历史义务、数据根、quota、grant或恢复语义。
RT2失败则RT3/H01/Q4/H11保持NOT_RUN；核心失败保留实际结果，不以再次提交抵销失败。

交付记录区分代码修复、离线/CI验证、运行时准备、journal维护和三个核心verdict。
任何一项未完成都明确标注；不会把另一端发出的新任务说明计作功能成果。
