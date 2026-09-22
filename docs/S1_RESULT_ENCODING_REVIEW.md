# S1 Result UTF-8 故障隔离复核

日期：2026-09-22。输入主干 `e2c5f3fd512e0ecb115345743d140640649a01bc`；本地首候选 `e52ed11e9b7d174f98fba879a6f983bbf92e3de5`，发布产品候选 `89d6b8d807287396d4bac102d5fa8057558c3c7e`，共同 tree `487136f7887e8525145a56129868ed549e68748f`。两个候选均直接继承输入主干，源码树逐字节一致。GitHub 连接恢复后，通过授权接口建立可发布提交；发布候选重新构建并独立验证。本记录属于发布候选的后续文档提交，不改变受测产品字节。

Owner 要求再次深入复核、发现问题直接修复；既有全量测试与直接提交推送 main 的授权继续适用。工作范围仍为 S1。固定规则原文采用此前直接取回并保留的原始字节，核对其 Git blob 与 AGENTS 中的 SHA-256 后阅读；首轮私有接口不可用；恢复后再次通过 GitHub 连接读取同一固定上游规则。公开节录仍不认定为已获等价采纳。R、A、Owner 决定、C 和祖先关系保持不变，三份批准文档字节未变。

## 确认并修复的问题

上一轮处理了无法形成 canonical UTF-8 摘要的 Task，但 Result 的形状校验仍可能抛出裸 `UnicodeEncodeError`。ASCII JSON 中的孤立代理码点转义可通过 UTF-8 读取和 JSON 解码，在 Result 再编码时失败，绕过已有的证据隔离逻辑。

本次只在 Result 形状校验处将此异常转换为 `result_invalid / indeterminate`，由原有调用方映射到相应入口错误。原始文本不替换，原始证据不改写；协议、摘要算法、尺寸限制和遗留非有限数行为不变。

| 入口 | 旧行为 | 验证的修复行为 |
| --- | --- | --- |
| 远端 canonical Result | 裸异常中断轮询，后续正常 Task 被阻塞 | 原 Result 字节保留，记录 remote_result_invalid 冲突屏障，后续 CAS 正常执行 |
| 本地 outbox | 裸异常中断整批发布 | 原始字节隔离到 quarantine，后续健康结果仍可发布 |
| receipt 内嵌 Result | 裸异常阻断后续任务 | 原 receipt 保留，记录 local_receipt_invalid 屏障，禁止盲目重放 |
| Controller wait | 裸异常与 traceback | 返回有类型的 remote_result_invalid / indeterminate，CLI 退出码 3 |

新增 6 个源码测试覆盖嵌套值、对象键和错误文本的异常编码、合法中文与 emoji、原始证据保留、健康任务继续，以及重复轮次不重放。安装态增加 4 项检查，将远端 Result、outbox、receipt、Controller 拒绝和健康 CAS 串联，并核对重跑前后的持久文件摘要。

## 验证结果

| 项目 | 实际结果 |
| --- | --- |
| 输入主干全量 pytest | 291 passed，0 skipped |
| 输入主干新增缺陷红测 | 4 failed，均复现 UnicodeEncodeError；作为预期失败保留 |
| 修复后定向回归 | 32 passed |
| 本地首候选全量 pytest | 297 passed，0 skipped；340.690 秒，RUSAGE_CHILDREN maxrss 119240 KiB |
| 发布候选全量 pytest | 297 passed，0 skipped；341.150 秒，RUSAGE_CHILDREN maxrss 118984 KiB |
| Python 编译、wheel 构建、独立安装、pip check | PASS |
| Linux shell 语法、Git 对象完整性 | PASS |
| 发布候选工作区外安装态完整验收 | PASS：93 checks / 291 commands，0 skipped；282.014 秒，RUSAGE_CHILDREN maxrss 54588 KiB |

发布候选 wheel SHA-256：`31f5132b51a10360c8ab35eef9c345f3d87293e369f7228c4d2a871be11d18c2`。

本地首候选 wheel SHA-256：`9b61267f83b38edfe01a48a8fc857d6ee9e6e7d619d1d3210740b84bc5eecbe6`；历史运行绑定原安装包，不与发布包混写。

载荷摘要：`3f3d141395d3d56e0cf599491c09e4c491a5f83c998d0b56ed38898a0105968f`。

独立字节核对脚本不导入产品代码，直接比较 Git 对象、源码、wheel、安装文件及 RECORD：89 个源码 blob、23 个载荷文件、29 个 wheel 成员、28 个 wheel RECORD 摘要和 33 个安装 RECORD 摘要通过。空摘要的生成 bytecode 项不计为已校验的 RECORD 摘要。发布候选还逐个比较生成 bytecode 与对应源码的编译结果；没有把空 RECORD 摘要当作已核对。另一份独立脚本核对完整安装报告、291 条命令的预期/实际退出码、582 份日志摘要、原始异常证据、任务摘要、业务状态、持久屏障和重复轮次后的业务文件，均通过。本次没有组织多个审计者，不将多份脚本结果描述为多人独立审计。

RSS 是已回收子进程的 RUSAGE_CHILDREN maxrss，不是同时运行的进程树内存总和。本轮云端验证不等于完整 GitHub CI 矩阵。

## 必须保留的失败轮次

第一次安装态验收在 64 checks / 209 commands 后 FAIL：内容读取故障恢复用例 LH9804 中，Worker 与 Controller 命令均符合预期，成功结果一致，但 outbox 文件仍被观察为存在。现场普通文件先归档，合成 dangling symlink 的目标另作补充记录；随后在该现场进行有记录的诊断重跑，观察到确认远端一致结果后 unlink 生效，且业务文件未改写。诊断成功不改写原 FAIL，也不能还原首轮异常时序。

第二次使用新 fixture、同一安装包及未修改的断言，在 33 checks / 107 commands 后 FAIL：投递超时恢复用例 LH9995 同样观察到 outbox 文件仍存在。该现场另行保留。两次失败均发生在本次新增 Result 编码用例之前。

历史复核曾记录工作区文件同步异常，这只提供调查方向，不能据此确定本次根因。最终隔离验证将源码副本、全新 runtime 和完整验收 fixture 移至工作区外；候选、wheel 字节与断言不变。两次原始失败的产生时序和根因仍未确定，不能用隔离通过倒推问题已解释或已修复。

恢复连接后，对第二份已归档现场执行带 Python audit/行跟踪的诊断，观察到远端一致性确认后调用 os.remove、pending 消失；业务文件、receipt 和 canonical Result 字节不变。随后 10 秒内的 200 次观测均未见 pending 重新出现。没有基于未证实的环境归因修改产品代码。

首候选第一次工作区外隔离运行因执行环境离线中断：保留 260 条完整命令记录及 520 份校验通过的日志，第 261 号命令目录没有完成记录，最终 report.json 不存在，整体记 INCOMPLETE，最终退出码不可用。新增 Result 编码链路的证据已生成；这不代表该轮完整验收通过。发布候选使用另一组全新隔离目录重新执行完整验收。

## 范围与交付状态

- 云端 Linux x86_64 / overlay、Python 3.12.14、Git 2.51.1；使用本地合成 Git/SSH fixture，不代表真实 SSH 身份认证或 GX10 / aarch64 / ext4 实机验收。
- CLI 命令退出码与 Result 业务状态分别核对；退出码 0 不自动表示业务 succeeded。
- 本修复属于支持 artifact-ledger 后续验收的 S1 工具修复，不构成 ledger A2 完成证明。Windows、现役服务切换、S2 和 A2 本轮均未执行。
- 仅发布修复、测试、验收程序和本摘要；不加入 SOP 历史、规则全文、实机原始证据或许可证。
- 首轮 GitHub 连接曾返回 HTTP 400 / Invalid MCP request metadata，直接 Git 推送预检也缺少写入凭据；这些失败按原状保留。后续授权 GitHub 连接已恢复，交付采用准确发布候选及其文档子提交；通过远端 ref 复读核对最终发布结果。

## 下一步 GX10 S1 复验输入

本轮交接产品输入 D 固定为 `89d6b8d807287396d4bac102d5fa8057558c3c7e`，tree 为 `487136f7887e8525145a56129868ed549e68748f`。执行既有 [GX10_S1_RUNBOOK.md](GX10_S1_RUNBOOK.md) 的隔离流程时，本次 checkout 使用此 D；原任务书的初始 D 和历史结果不改写。

原任务书的“D 历史恰为 7 个提交”、139 项源码测试和 25 checks / 66 commands 仅适用于原始候选。本次应保留完整修复历史，验证 C 是本次 D 的祖先以及三份批准文档相对 A 字节不变；本轮云端参考为 297 项源码测试、93 checks / 291 commands；GX10 数量与结果以实机实际记录为准。

GX10 复验重点增加两处 outbox 恢复观察：远端确认后的 pending 删除、随后重复轮询是否保持业务文件与回执不变。再次出现残留时保留目录状态、原始字节、命令时序与相关进程观测，不能直接删文件再计 PASS。只有取得完整实机结果后，才能据此准备 S2 切换方案；本记录不批准切换服务，也不关闭 artifact-ledger A2。
