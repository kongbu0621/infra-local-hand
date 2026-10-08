# 有界预检与条件核心的单次交付

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-NAMES-CONTINUATION-v1` / NC1–NC3，依[需求](REQUIREMENTS.md)
及[架构](ARCHITECTURE.md)执行。本计划不提供现场命令。
输入修复 `13ba2757aef0f3e48d334c371c367db7dc61a7ec`；只读交接记录
`82597b78824fe33cd0a1352954b36bb9a6f8041d`。两者证据不替代未来新D验证。

## NC1：先完成表示修复、完整绑定与冻结

1. 本三文档形成准确A，Owner B明确原R、准确A、NC1–NC3、新格式及一次维护/条件核心，
   同时决定main发布与需求中旧08a五件最小索引披露。独立C只记录准确B与CLOSED，
   三文档原字节保持，D承接C。不提前写生产/测试源、原型、配置或可执行caller。
2. 只读已有08a五件保留副本，对照原TC2私有索引、已有预检/execute、marker/manifest/
   receipt及流关系，沿原保护读取核验。获批后仅公开basename/bytes/SHA-256，保留
   前三代批准pins与全部原文/消费/UNKNOWN。不因缺席、冲突而重采或改变原pins。
3. prior-attempt加入第四代准确manifest/receipt v5失败解析，08a嵌套resume仍指原三代；
   维护host/guest固定08b与九名。二十旧原件和十六旧后续缺席名贯穿普通预检、消费前
   同FD重读和核心读取，保护条件与跨集合inode去重保持。
4. 维护host实现manifest/receipt v6、preflight v5；只在短预检将resume改为完整resume
   的canonical含LF摘要。生产者从实际已验证manifest取值，解析器验证候选固定历史，
   execute重建完整manifest并交叉核对原nonce/双钟/计量。三处不得分开交付。
5. 同步contract/freezer、approved-input、package/entry、独立dispatcher/bootstrap和
   返回消费者：transition v5、reconciliation/history v9、capacity v8，完整四代投影。
   每设备五代6480 MiB/1850及含核心6544 MiB/1866、五代各120 CPU-s均保留。
   源码校验仍必须绑定准确R/A/B/C及D祖先；dispatcher摘要以新D审查结果为准。
6. 先完成离线构造与双方校验：实际二十件输入、四代全历史和原最大计量/20位时钟；
   预检≤4096 B、transition≤65536 B、approved-input≤1 MiB、包≤32 MiB、两源各
   ≤98304 B和原bundle/stream限额。超过任何原限额即停止，不以现场试跑定位。

离线验证必须对应本次失败模式及绑定边界：

- 短预检缺/多字段、旧v1–v4、非小写/截断/错摘要、无末尾LF、三代摘要、错scope/session/
  R/A/C/D、错manifest/nonce/boot/原钟、计量类型/上限/清零；4096/4097 B入口界限。
- 修改完整历史任何授权、D、顺序、原件pin、旧消费或UNKNOWN；把攻击者新摘要同时
  填入交接仍必须失败。摘要看似相同但缺少原件、旧schema/嵌套关系错误同样拒绝。
- 逐件缺失/篡改/链接/metadata漂移、错事件/流/nonce；十六缺席名出现、新九名任一
  已存在或部分marker，消费前同FD重读变化。上述准入反例在marker和SSH前停止。
- host及独立guest消费者在完整新成功上结论一致，拒绝旧失败冒充成功、新旧boot串用，
  不用未发核心批绕过维护；保留原H01→Q4→H11的准入及live finalizer语义。

7. 跑受影响现有源码测试、Names/模板/systemctl及真实JournalDevice的隔离验证、合成
   完整贯通和独立installed检查。原生测试只用私有临时总线/单元，不查真实管理器；
   缺少本机v255格式库的跳过如实保留，结合准确修复CI，不虚称本机原生PASS。
   既有已验证且字节未变的证据可准确复用；未来D必须有自己的准确首次CI，不能借输入
   修复3/3代替。首次失败及环境限制保留，不机械重复无关全套测试。
8. 静态核对既有八输入、四旧核心批、四代失败维护、固定来源与参数；该步骤不观察VM、
   SSH、执行维护预检或生成真实核心包。完成发布、准确CI、安装证据、来源摘要及新D
   冻结后，才形成一个维护caller与一个条件核心caller。旧caller和冻结副本保持原样。

## NC2：唯一08b维护

可信单管理员前提成立且NC1全部完成，普通身份复用原安装、SSH、输入及五镜像。
只运行一次普通预检，成功后同起点/nonce/manifest及累计CPU/RSS执行，900s双钟、
780s修改截止和最多两次固定SSH不变。所有原件、目标、来源、容量和原准入通过后
才创建marker；正常静止/关机、旧pidfd退出、完整独立备份、镜像增长/比较、一次原
配置启动及ext4/UUID/内容/容量检查完整通过才VERIFIED。

开始即消费；失败、拒绝、超界或超时即停止，即使marker未建也不退款。保留实际动作、
退出/EOF和UNKNOWN，无就绪探针、重连、第三连接、补采、清理、恢复或重试。
NC2失败则NC3 NOT_RUN，不自动申请另一窗口。

## NC3：原核心接续和如实交付

仅完整NC2原件验证后，同一冻结D保护读取四旧二十件和新八件成功原件，构造完整
transition v5。核心caller沿原独立900s双钟/800/750s界限，双构包/独立解析、来源/
容量、BIND、新HELLO、旧历史/目标管理及全部原准入通过后，最多发一次原
`lhqcore-20261007a` H01→Q4→H11；任何原核心对象已存在即停止，不换session/任务。

原live finalizer决定三case实际结果；失败保留首因与已有结果，不重放或补采。
交付准确D/CI/冻结、实际窗口消费、维护及核心verdict。未完成项明确NOT_RUN或BLOCKED。
批准后准确批次内不逐项询问，实质变化仍按原R处理。原文私有，公开仅获批脱敏记录
及旧08a最小索引；不含原现场正文、环境、绝对路径或新08b原件索引的自动披露。
