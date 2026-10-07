# 同一次修正、验证和维护接续

Authority：Owner；**PROPOSED / Gate OPEN / NOT APPROVED**，仅 W1–W2。
遵守[需求](REQUIREMENTS.md)和[架构](ARCHITECTURE.md)。本计划无可执行现场命令。

## W1 完整修正和冻结

先冻结三文档准确A，取得明确Owner B，记录独立bookkeeping-only C，之后才实现D。
不合并A/C/D、不改旧批准或消费记录。只有本范围新增预算、协议和源长度被明确批准后，
才能写入相关源码、测试和配置；已有未受影响CLOSED开发不暂停。

源码只修改两个维护实现和直接相关测试：

1. host `_fd_snapshot/collect_image_writers` 加同调用的固定计数状态与调用前收费；
   三类stat全部计入，移除旧FD_TOTAL门，保留所有身份/writer/覆盖判定。
2. guest `writer_payload/WRITER_ENTRY/writer_failure/WriterProtocol.validate/observe`
   接v2 progress；父层保留合法失败前缀。`WriterObserver.binding` 及 source admission
   绑定本范围准确A/C、政策、文档、payload/argv和原输入，不接受旧v1交接。
3. `growth_sources/source_bundle/GUEST_LOADER` 仅实施规定的源长度变化；reader、descriptor、
   root payload和各传输界保持。冻结前核验实际两源、生成payload、bundle及完整argv尺寸。
   不以删校验、删pins、新模块或无边界压缩/解压替代尺寸准入。

定向验证必须同时执行源函数和真实生成payload，并覆盖：

- 预算恰等于2097152可用，第2097153次候选在stat之前拒绝；三类共用预算、异常不退款、
  每snapshot65537项在收费前拒绝。断言未发生多余stat和后续task读取。
- 超过旧262144逻辑条目后仍执行后段匹配FD/mapped writer检查，保留线程私有FD表用例；
  不因源函数或生成路径忘记计费产生绕行，不通过跳过线程或用缓存PASS减少工作。
- 协调高task/FD/maps数据，联合预算边界、maps512 MiB/单文件1 MiB、身份/集合漂移、
  读取错误、认证/扫描期限和后扫描失败；复用有界夹具，不能一次分配累计maps总量。
- v2成功/失败/早期request-null/REPORT失败与父层传播；固定字段、类型、关系、4096 B界，
  缺失/额外/负数/bool/float/伪complete/串request/旧v1均拒绝。保留双流/EOF/真实退出语义。
- 98304 B边界仅对两个维护源和guest bundle源生效；其它输入65536、固定payload32768、
  bundle49152/393216及argv65536仍拒绝越界。旧授权和本范围文档/祖先/来源漂移仍拒绝。

先完成相关journal/proc/payload/transport/coordinator回归，再核实准确D相关CI。
保存真实PASS/SKIP/失败；隔离规模测试不冒充实际宿主吞吐或完整现场准入。
本地Codex完成云端不能替代的普通身份原私料静态核验、准确源码/工具/输入冻结及交接准备。
不重新安装，不调用真实sudo/proc/SSH做预探测，不复用已消费的旧冻结交接。

## W2 一个窗口，条件完成维护

W1所有条件完成后，Owner在已有真实本机前台终端使用现有认证。沿原CLI的终端资格→
建立Window→冻结/核验输入顺序开始唯一替代预检，不推迟或刷新时钟；checkpoint各调用一次。
只有全部原门通过，才在同一窗口执行未消费的原关机、备份、增长、单次启动及guest增长流程。

失败时交接摘要保留原首因、已经取得的progress或明确缺失、marker/SSH/动作次数和退出事实。
不截成只有N/MAX的单行，也不停止后补读来凑齐统计。不能把prefix当全机总量，不能依据
用量自动提额、重跑或开新窗口。原现场和历史变量/结果全部保留。

只有原内容/容量/身份/退出/完整receipt通过才宣布journal维护成功。状态回写须明确W1源码
完成和W2现场结果分别是什么；没有现场成功就不得宣布已经进入H01/Q4/H11。

## 核心接续的已确认缺口

这部分是后续路线定位，**不包含在W1–W2实现/执行授权中，也不是已经准备好的第五批发行**。
现核心dispatcher要求旧HELLO与新HELLO处于同一boot，且只消费03a/05a/05b三旧profile。
本次维护会重启guest，另有已消费05c必须保留。因此仍需完成准确的核心接续修订；
设计可提前准备，发行和执行以合格维护原件为条件。不能重跑旧包、改旧boot或删除boot校验。

已定位需要的最小接线：

- 在固定维护consumed/events/pre/post/receipt/pidfile原件之间验证准确D、步骤、nonce、
  原输入、旧VM退出、新VM及五镜像、boot/内容/容量关联；只信receipt状态字符串不够。
- `q2_core_prior_attempt/q2_core_approved_inputs` 和dispatcher增加05c第四旧严格profile；
  新boot只由合格维护代次派生并与当前HELLO核对，旧boot/InvocationID和UNKNOWN不重写。
- contract/freezer/package/entry/独立consumer接一个新固定核心批身份和发行，保留四旧、
  两诊断及维护全部承诺；完整静止、配置、配额和容量准入继续执行。
- 仅一个新核心批按原H01→Q4→H11顺序和900/800/750s合同验收，原runtime/wheel/harness
  及H11自身原ledger/unit语义不改；不能把维护窗口延长成核心窗口。

这些位置已识别，尚无接续实现或维护原件。提前说明此边界，避免把“扩容后即可直接跑旧包”
作为承诺；支线继续暂停，生产E3监督仍未验收。
