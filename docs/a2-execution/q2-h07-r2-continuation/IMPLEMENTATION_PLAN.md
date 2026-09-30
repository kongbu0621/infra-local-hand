# H07 第二轮失败后的限定修复与最后一轮：实施方案

- Authority：Owner；状态：**PROPOSED / Gate OPEN**；Scope `LH-Q2-H07-R2-CONTINUATION-v1`，仅 V1–V4。
- [需求](REQUIREMENTS.md) → [架构](ARCHITECTURE.md) → 本方案。R、旧 A/C、输入历史及所有不变边界按需求。
- 本提交只形成受影响方案。新 A→准确 Owner B→独立 CLOSED C→实现 D；不在 A/C 中混入本变更 source/test/runtime 配置。

## 输入事实和当前已完成工作

第二轮原件和严格失败留证已在 `9a5fb7488dcd6988b6c7d0c5c45cdf87d998dad6`。准确源码研究、现有收件及编译检查见[本轮准备复核](../Q2_H07_R2_PREPARATION_REVIEW.md)。这些是方案依据，不能写成新方案已实现或云端六案通过。

原 U2 测试曾假设仓库永久没有第二轮索引。发布合法 U4 留证后，既有定向测试实际出现1失败/316通过；已将缺文件负例隔离，并检查真实索引仍拒绝第三轮。这个修复不改实验代码或准入；它与本新架构分开交付，不替代 V1–V4。

## 阶段和文件

| 阶段 | 明确交付 | 开始/完成条件 |
| --- | --- | --- |
| V1 | 精确 A 基线、Owner B、独立 C；版本化第二轮历史接受及来源准入 | 文档审查无未解决阻断后才请 Owner 决定；新源码从 C 下降 |
| V2 | 有界世代创建/退休、固定 helper 目标推导与原 FD 绑定 | 只在固定实验目录内；与原限额/权限/双钟同时验证 |
| V3 | native v2 / report v3、诊断及收件/停止传播、定向回归 | 旧原件校验不变；新负例逐项通过；纯编译/解析与 kernel 证据分开 |
| V4 | 准确 D 普通 CI、只读准入盘点、一次最后实验及脱敏结果 | 所有前置成立才派发；失败也消费最后轮；之后不再实验 |

可变程序边界仅 `tests/e3_host/spikes/q2_cgroup_fence/` 中 `helper.c`、`run_fixture.py`、`verify_receipt.py`、`continuation.py` 及其定向测试；必要时按同一职责在该目录拆分，不能加入生产 loader 或 wheel。`account_evidence.py` 的已批准账户合同保持；接口适配不得改其身份/命令/清理判据。

workflow 只调整 `.github/workflows/q2-cgroup-fence-spike.yml` 的准确新 C/版本准入、round 固定为3和明确修复原因；保持 manual-only、固定 hosted label、attempt1、main、只读权限、action pins、15分钟、并发不取消、allowlist上传与30天保留。不增加 dispatch API、push/PR触发或自托管路径。

文档/历史处置登记在原 evidence 和 governance 目录；原两轮验证索引及原件保持字节。新增脱敏历史接受记录只引用固定事实、摘要、准确 B/C；不能内嵌原机器报告。新 report 的 source closure 纳入该记录、新三文档和决策，校验当前工作树/准确 Git blob/预置摘要，不能只信汇总布尔。

## 实现顺序

1. 独立 C 只登记准确 A/B，不改变三文档。先设计明确版本分支，再改生产实验路径，禁止临时放宽旧校验使代码先通过。
2. `continuation` 增加本 scope 专用版本，绑定旧两套 A/C、新 A/C、旧两轮原摘要/脱敏索引、新 run 与 boot。只准 used_before=2、limit=3、round=3、attempt=1。旧 clean REJECTED 路由不承担本次恢复；未知 schema/事件/原件漂移一律拒绝。
3. 建 E 一次；严格固定世代 PROBE/C1…C6。每代 G/B/S/W 先登记实际对象、配置和读回权限/资源；没有全部就不启动该代。helper 根据原固定 mode/case 推导名字，不接受 caller 自选路径。
4. 每代原 helper 已退出并取得双 EOF、其原回执/原 pidfd/树空/资源信息齐备后，验证实物身份并叶到根退休。只在该代要求的继续判据及清理都满足时建立下一代。预期 C3/C6 不补回丢失的任务身份/guardian seal。
5. 每代保存 before/after/retirement 与固定世代身份；FD 责任明确关闭，rmdir 成功不是原进程退出替代。可见 dev/ino 重用不回连旧对象，不通过字符串 PID 追认身份。
6. 追加固定启动器提前退出、K_ARMED 拒绝诊断，保留原退出码与事件时序；不增加探针、不改变故障注入点或允许任意 payload。
7. 报告保留第一失败和后续校验问题，结构/时间/错误列表均有界；新诊断不参与造成功。新版本通过完整真实路径构建→序列化→校验→派生的离线验证。
8. 重跑受影响离线套件和原 helper 解析自测；编译 C11、`-O2 -Wall -Wextra -Werror`。所有产物隔离，禁止在当前云工作区或 PRO6000 建真实账户/cgroup/probe。

## 有针对性的验证矩阵

| 风险 | 必需证据/反向用例 |
| --- | --- |
| probe后只修一次，后续仍复用 | 七代固定顺序；每次kill后的代不再接受创建；非法代号、跳例、同代再开拒绝 |
| 跨例对象混淆 | 固定相对名/代号/持有FD一致；同名替换、旧FD、跨代回执、dev/ino重用、错代资源样本拒绝 |
| 退休不足却建立下一代 | helper未退出、任一原EOF缺失、B/G非空、rmdir失败、身份漂移、预算不足均停止；不能无条件finally后继续 |
| 新对象绕开原资源界 | E保持同一对象；每代G/B限额读回；最大5个可见登记目录/29次累计创建；不把内核延迟释放混作已回收；新代CPU/memory/pids事实各自绑定，E累计观测保留 |
| 计时刷新 | prepare/cases/cleanup共享既定阶段窗口；同例原双钟不重建；晚到退休不回填按期fence；无额外7×30秒清理 |
| 早退被摘要掩盖 | S在credentials/armed之前/之后退出、K_ARMED拒绝、G摘要与独立事实矛盾均保留原序号/退出；缺绑定不变成功 |
| 末次错误覆盖首因 | 单失败、多失败、cleanup失败、校验失败、超长列表、报告尺寸自收敛；primary_failure一经写入不可被后续替换 |
| 版本穿透 | schema1/2原件走原规则；v3缺新字段、类型错、未知字段、伪版本拒绝；旧报告不注入默认新事实 |
| 历史接受泛化 | 改run/attempt/D/artifact/index/报告摘要、删首轮、交换历史、boot重用、添加第3个先前run全部拒绝 |
| 仅stub验证准入 | 完整新版本报告及来源闭包进入真实收件器；不得用替换derive_report的stub宣称第三轮端到端可达 |
| 条件成功偷换 | 新异常及C5 INCONCLUSIVE不资格化；C3/C6只允许其原预期缺证且外部cleanup已证；six-case期待逐项保持 |
| 副作用前拒绝失效 | 错SHA/脏树/无C/错误round/attempt/预算/boot/历史在账户、构建和cgroup前拒绝 |

旧原件回归必须保留首轮 UNKNOWN/cleanup=false；第二轮原 report UNKNOWN、整份收件错误 REJECTED。新历史准入不调用“改写原状态后再验”的办法。

## 第三轮派发前的准确闭合

实现 D 发布后执行原普通 CI，核对其真实 Linux/Windows/collector 结果。既有旧 CI 成功不能替代新 D；跳过不能记为通过。先把修复/离线依据固定在文档，再选最终准确 HEAD 完成普通 CI，避免把该 CI 的自身run id再写回同一HEAD制造循环。

派发前记录可独立定位的只读观察：准确 D与tree、相对第二轮的受影响source摘要、普通CI run/attempt/head与结果、新C祖先、原两轮报告/index摘要、完整workflow运行/attempt盘点及额度2/3。该准入记录可作为独立保留证据，不要求再改待派发HEAD；实际报告仍绑定准确执行D。

只允许在 GitHub 页面手动派发 round3/attempt1；输入准确 expected_commit 和经复核的生命周期/诊断修复理由。动作回应不明先查run，不补发；页面不可用保持未派发。取得run id立即消费3/3，包含前置拒绝/UNSUPPORTED/setup失败。

本轮先核验标准hosted VM事实、全新boot及目标不存在，再执行一个probe和C1–C6各至多一次。任何新增非预期缺项、清理未证或超限立即停止后续例。托管标签、上游源码研究、单独probe或普通CI不代替实际内核/权限/六例事实。

## 留证、结束与回退

保留准确原ZIP、manifest、report、native各例和日志摘要；公开仓库仅脱敏结论/摘要，原机器产物另存。各世代是否创建/运行/退休分别记录，未运行不填成功。artifact留存失败也是事实，不能借机再次执行。

本轮无论结果如何均用尽额度；不启动第4轮、不重命名实验避开配额。可回退到停止派发和已知源码状态，但不回退历史、抹除失败或复活旧对象。若需求/权限/预算/环境继续变化，按原R重新处理受影响范围。

完成不要求根因动态归因全部解决，但必须把未捕获的信号来源和未建立的现场事实明示；不将本方案变为内核资格普遍证明。原Q2仍NOT_ISSUED，未批准任何PRO6000/GX10操作或产品部署。
