# sudo 修复后核心单次验收：实施方案

- Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
- Scope：`LH-Q2-CORE-POST-SUDO-ACCEPTANCE-v1`，S1–S3；R及精确对象见[需求](REQUIREMENTS.md)，合同变更见[架构](ARCHITECTURE.md)。
- 先三文档准确A → Owner逐字决定B → 独立bookkeeping CLOSED C → 后续实现D。新范围未批准前不写实现、fixture或执行程序。

## S1：只接齐新增一次核心验收必需部分

1. 读取两旧固定发行D及十原件profile；独立审查第二旧sudo错误前的实际调用顺序，保留历史UNKNOWN。
   不要求恢复未保存的sudo原始stdout，不新增现场连接取证。材料只来自既有本地原件和固定Git历史。
2. `q2_core_delivery_contract.py`、entry/bootstrap/dispatcher同步需求全部新身份、UUID、projects和准确新A/B/C来源。
   loader无新增行为。先计算field尺寸，不能为通过cap删校验；所有旧A/B/C和已批准修复链保持。
3. `q2_core_prior_attempt.py`、approved-inputs/obligation builder及独立消费者按架构扩为恰两个固定profile。
   新schema用显式严格消费者，拒绝混合旧新版本；第一批原pins/结构不放宽，第二批使用固定SHA/9072B及原role上限。
4. dispatcher的两旧A/B核验、逐device双承诺、原新批准入和host192MiB/48条件接回现有链。
   helper次数/真实usage计入已有collector，CPU/memory/pids归原carrier；`native_children_started`仍仅原quota native children、上限16不改。不复制一次观察为两次，不漏掉第二旧scope/承诺，不把历史unknown计0。
   跨批前置3GiB/384和通过后新批原2624MiB/1160语义在验证和返回中一致，不能仍报告旧两carrier保证。
5. 同步finalizer和独立consumer对两个prior记录、三行host条件、新manifest/D/原窗口的完整交叉校验。
   六文件、82输出、包/wire和资源上限不加宽。准确release allowlist在S2完整通过之前保持空。

## S2：消费机会前的完整验证

必要回归集中在本次真实风险：

- 两个profile各自成功；混用零输入与非零输入、wrong D/package/manifest、缺件、错误hash/总长度、重复字段/多HELLO、篡改历史truth均拒绝。
- 第一/第二旧任一active、populated、不同boot/Invocation、父/inode漂移、未找到完整属性、超时或A失败均停止；A失败不执行B，不启动安装/case。
- 两旧各A/B的不同合法分支可以分别存在，但每旧自身A/B必须一致；漏第二旧、复制记录、排序/摘要串线均拒绝。
- 两旧全额承诺和三批host条件容量不足拒绝；更早guest义务完整保留、hostUNKNOWN不填0、无退款。
- 所有新身份与两旧隔离，21project IDs及派生units完整；固定名字冲突拒绝，绝不现场换名。
- 真实host builder/parser→HELLO/BIND→guest包parser→marker结构回构，保留writer字段和basename早拒绝。
- 继续sudo正式来源标题/TAB/无Defaults正例、未知source/权限拒绝及详细错误码穿过真实bootstrap.main的回归。
- H01正常结果、Q4运行中取消、H11自身ledger恢复、usage与独立证据消费者均维持原完整语义；synthetic结果不冒充现场。

冻结准确D后完成定向、完整source、独立installed verifier与准确SHA的CI。报告真实PASS/SKIP，不用测试wheel替换原现场wheel。
本地Codex复用真实私料，完成全部source-aware输入、十原件和两套独立构包/解析；新D/包不可沿用432f3f4旧身份的内存测试结果。
上述离线验证通过后，单独登记仅对应已审dispatcher SHA的发行提交，不同时改变field代码。核对最终发行D的准确SHA及所需完整source/installed/CI和私料双构包结果；任何失败即关闭发行，不进入现场。
离线复核caller结束后不得复用其writer/window。随后正式caller在同一新原900s内，绑定这个最终发行D，重新核验held anchor、管理入口、writer、十原件、双构包、192MiB/48及六名absence，全部通过才消费marker/request。
正式窗口内不再修改Git发行提交或替换已绑定D；release digest只允许已审代码进入原检查，不能代替这些当前消费条件。源/A/B/C/包/窗口不相符均停止。

## S3：一次执行并交付真实核心结果

由持有私料的本地Codex复用现有SSH/管理配置，创建唯一05b marker、发送唯一05b carrier。
该carrier按原准入和双旧静止检查通过后，create-only新批安装并执行H01→Q4→H11；不重装旧安装、不改sudo/账号/权限。
没有额外SSH probe、现场补采、自动重试或失败后的退出检查连接；任何失败保留已取得的六文件子集，消费事实不撤销。
独立验证真实结果/资源/退出及原live finalizer；记录准确D/tree、包摘要/bytes、十旧原件绑定、三个case verdict、缺项和明确停止原因。
两个旧历史UNKNOWN单独保留；一次新成功也不会把旧记录改成PASS。

云端负责实现、审查和Git/CI；本地Codex负责私料验证及获准的唯一现场执行，不要求Owner手工反复搬运材料。
本A终点是一次核心验收结果，不含生产部署；E3限制及namespace/watchdog、E4–E6、NAS等暂停范围保持。
若本次失败，本scope在保留失败后结束；不能通过续跑、改名或删marker自动变成下一次授权。
