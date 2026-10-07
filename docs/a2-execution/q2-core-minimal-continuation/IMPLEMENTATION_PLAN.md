# 一次删减，条件完成核心链

Authority：Owner；**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-MINIMAL-CONTINUATION-v1`，K1–K3；遵守[需求](REQUIREMENTS.md)和
[架构](ARCHITECTURE.md)。本文件不含可直接执行的现场命令。

## K1 只实现主线所需差异

本三文档形成准确 A 后，取得 Owner 对 R/A/K1–K3 的明确决定 B；独立 C 仅记录批准，
实现 D 承接 C。此次用户的方向指令不伪写为接受尚未披露取舍的准确 B。
不要求分别批准删一个调用、修一个绑定或增加第四 profile。

1. 两个 journal 维护文件移除 host 全宿主扫描/八调用/root认证及生产报告依赖；保留
   目标/备份/内容/容量检查。同步相关测试和源准入、CLI、manifest/receipt 新版本。
   普通预检交接保留同窗/nonce/累计计量；旧 handoff 必须被新入口拒绝。
2. 在现有 `q2_core_prior_attempt.py` / `q2_core_approved_inputs.py` 接受保护维护原件
   验证、固定 transition 对象和05c第四profile；只读已有原件，不新建通用采集器。
3. 在 contract、freezer、package、entry、dispatcher、bootstrap 完成07a身份、新批准/
   四旧/维护关系、八 SHOW、host容量及guest保留义务的对应绑定。
   更新原独立返回消费者和安装验证入口；runtime/wheel/harness/loader不变。
4. 在已有定向测试中验证真实维护协调路径不会调用host `/proc`全枚举或root observer，
   目标身份失败/原QEMU未退出/备份或内容错误仍阻止修改，旧handoff/跨窗/计量重置拒绝。
   验证维护原件交叉关系、缺件/截断/错误D/nonce/顺序/失败状态/新旧boot串用拒绝；
   四旧任一缺失/活跃/旧scope在新boot重现拒绝，历史UNKNOWN和完整承诺不被清零。
   贯通原host构包→guest消费→H01/Q4/H11结果→host finalizer的合成链；替身测试不报现场通过。
5. 完成相关source、独立installed验证及准确候选CI。保留真实失败/SKIP，冻结准确源/
   参数/上限。直接复用未变的原件及其固定验证，不重做已完成的无关诊断或整仓专项。
   本地Codex复用已有私料完成维护交接和核心构包能力检查；此时不试连、扫描或操作VM。

必须先把两段实现都接齐并验证，再进入K2。不能维护结束后才发现没有实现新boot消费者。
真实维护结果尚未出现不阻止K1合成验证；它仍阻止K3真实包发行。
只登记实际已审、已通过对应检查的准确dispatcher摘要；空allowlist不提前打开。

## K2 一个维护窗口

K1通过且可信单管理员前提成立后，本地执行者在现有管理环境开始一个替代窗口。
原八输入、工具身份/参数、同窗普通预检与execute再准入、一次marker和原两阶段维护保持。
不再启动host writer观察，不增加替代探针；旧窗口、旧变量/输出、旧安装和证据原封保留。
所有目标条件通过即按原顺序完成关机、备份、增长、单次启动及ext4增长，范围内不逐项停问。
记录真实维护结果与未执行的全宿主观察；失败停止，K3为NOT_RUN。

## K3 合格维护后一次 H01→Q4→H11

只在K2完整成功原件已产生后，复用K1准确实现进行保护读取和完整关系核验；绑定真实
transition、原四批/两诊断、原runtime/wheel/projection、07a对象，完成原双构包和独立解析。
核对准确源码及最终发行摘要/CI；若只是发行登记改变，证明field字节不变，并执行直接相关
发行/来源检查，未变的完整测试结果引用其准确基线，不机械地再跑一轮相同全套测试。
出现source/field实际修改则验证其影响，不用旧CI冒充新候选CI。

完成上述条件后，在新的原900s双钟核心caller窗口中重验管理绑定、输入、原件、容量和
create-only对象；一次marker/一次carrier请求。新HELLO必须与维护post匹配，四旧A/B当前
缺席、五池容量和原全部策略准入通过后，才创建新批原合同安装并依次执行三个case。
不复用维护时钟，不另发SSH就绪探针，不重复运行旧批或已消费诊断。

交付只报告三个实际verdict、任务输出/退出/取消/恢复证据、首因和NOT_RUN，以及准确
D/包/维护关系。只有原live finalizer完整通过才称核心完成。失败不自动申请或运行下一批，
不增加监控、重试、清理或恢复功能；保留现场供必要的针对性修复。

本方案批准前只交付文档和审查结论；没有新的现场次数，也没有声称代码已删减或核心已通过。
