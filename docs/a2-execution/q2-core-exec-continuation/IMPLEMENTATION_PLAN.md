# 单次维护与条件核心的实施顺序

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-EXEC-CONTINUATION-v1` / EX1–EX3，依[需求](REQUIREMENTS.md)
和[架构](ARCHITECTURE.md)。输入修复 `e2d27ca51317ccd449772d82a2366b2f3092711e`；
此文档不提供现场命令。输入修复CI不是未来新D的验证。

## EX1：两段完整实现、验证及冻结

1. 三文档形成准确A；Owner B明确原R、A、EX1–EX3、一次08c维护和条件原核心，
   以及main发布和旧08b最小索引披露。独立C只记录准确B/CLOSED，保留A原字节；D承接C。
   未获准确B/C前只做文档和已有代码/保留副本检查，不写新源、原型、配置或caller。
2. 沿原保护读取核对08b保留五件与原私有索引、已有preflight/execute、marker/manifest/
   receipt、事件及流关系；不回现场补证。批准后仅公开basename/bytes/SHA-256。
3. prior-attempt加入第五代08b原v6失败profile及其四代嵌套resume；保留之前各代解析。
   维护host/guest固定08c与九名；25旧原件、20缺席名进入原保护读取、消费前同FD重读
   及核心读取；元数据保护、上限和跨集合inode去重不变。
4. 准确新来源R/A/B/C/D绑定，manifest/receipt v7、短预检v6；完整五代resume与实际
   manifest摘要取值、解析器固定历史验证、execute重建/原钟/计量交接一起交付。
5. 同步完整核心链：transition v6、reconciliation/history v10、capacity v9，六代
   每设备7776 MiB/2220及含核心7840 MiB/2236，各120 CPU-s；保留旧全部UNKNOWN。
   同步host、独立dispatcher/bootstrap、回执消费者及准确dispatcher发布摘要。
6. 在原4096 B短预检、65536 B transition、1 MiB approved-input、32 MiB包、两源各
   98304 B及bundle/stream界限内，验证完整五代、最大计量和20位钟。实际数据或任何
   上限不满足即停，不用现场试跑定位，不放宽额度。

验证对应实际风险：

- 第五代原v6/嵌套四代关系、各代准确授权及五pins；错顺序、篡改/缺少/链接/元数据
  漂移、原事件/流/nonce差异、20缺席名出现、新九名任一已有，全部在marker/SSH前拒绝。
- 原短预检字段/4096–4097边界、旧版本、错R/A/C/D、manifest/nonce/双钟/usage、错
  摘要/无LF/四代摘要；即便同时替换历史与摘要也拒绝，不能从摘要补造缺少的原件。
- 完整成功原件到双方核心投影一致，拒绝旧失败冒充成功、新旧boot混用及未发核心
  绕过维护；保留原H01→Q4→H11准入与live finalizer结果判定。
- 已有Exec多命令、Names、模板/systemctl、真实JournalDevice隔离验证及受影响核心/
  维护测试。真实格式检查只调用本机纯格式函数，模板总线用私有临时对象，不查真实
  管理器；缺少环境就保留SKIP。首轮失败和限制如实保留。

7. 完成源验证及独立installed检查，发布新D，确认D自身首次相关CI和完整步骤；输入
   修复的3/3只能作为历史依据。已有字节未变证据可准确复用，不机械重复无关全套。
8. 只读核对既有八输入、四旧核心批、五代失败维护、来源/参数及原大小上限，不观察VM、
   发SSH、运行维护预检或生成真实核心包。完整验证后冻结同一D和两个私有caller；
   原安装、旧源码、caller、冻结副本与消费保持，未确认可信单管理员前提或有冲突即停。

## EX2：一次08c维护

EX1全门通过后，普通身份复用原安装、SSH、已核对输入及五镜像，只运行一次普通预检。
成功后同原点/nonce/manifest及累计CPU/RSS进入execute，保留900s双钟/780s修改截止、
最多两次固定SSH及全部原准入。正常静止/关机、旧pidfd退出、完整独立备份、镜像增长
与比较、一次原配置启动、ext4/UUID/内容/容量检查全部完成才VERIFIED。

开始即消费；失败、拒绝、超界或超时即停止，即使没有marker也不退款。保留实际动作、
退出/EOF及UNKNOWN，不发就绪探针、重连、第三连接、补采、清理、恢复或重试。
EX2失败则EX3 NOT_RUN，不自动申请另一窗口。

## EX3：原核心及准确交付

仅EX2完整原件验证成功后，同一冻结D保护读取旧25件与新八件，构造完整transition v6。
原核心沿独立900s双钟/800/750s期限，双构包/独立解析、来源/容量、BIND、新HELLO、
历史/目标管理及原所有准入通过后，最多发一次 `lhqcore-20261007a` H01→Q4→H11。
原核心对象任一已有就停止，不换session或任务，也不单独挪用条件权限。

由原live finalizer决定case实际结果；失败保存首因和已有结果，未完成项明确NOT_RUN
或BLOCKED，不重放或补采。交付准确D/CI/冻结、实际消费、维护及核心verdict。
批准后的准确批次内不逐项询问；实质变化仍依原R。原件私有，公开仅获准脱敏记录和
旧08b最小索引，新08c索引不得自动公开。
