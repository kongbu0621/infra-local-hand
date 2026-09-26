# Q2 账户准备失败后的限定接续：架构

- Authority：Owner；状态：**PROPOSED / Gate OPEN**；scope：`LH-Q2-PREP-RECOVERY-v1`。
- 依据 [需求](REQUIREMENTS.md)，原 fixture 准备三份文档与批准历史保留不动。

## 职责与信任关系

| 组件 | 职责 | 不得替代的事实 |
| --- | --- | --- |
| 恢复管理入口 | 现有管理通道建立一次最多 300 秒的独立 envelope；持有原 client、双流及停止责任 | 原准备时窗保持结束，不能冒充其原进程或延长其 deadline |
| 只读鉴证器 | 核对原 plan/receipt/命令记录/候选和现场，证明准确已完成与未交付边界 | 不从“目录不存在”单独推导 quota、manager 或运行从未交付 |
| 限定接续器 | 追加恢复意图；保留准确主组；执行一次修正账户命令及原未交付后续步骤 | 不调用普通首次准备入口绕过已存在检查；不更新原失败文件 |
| 原装配及运行入口 | 使用实际恢复事实、原计划和原安装候选，执行尚未发生的首次装配/发行/监督 | 不复用虚构的未来身份，不把恢复成功等同于 Q2/Q3 验收 |

恢复器为显式 test-only 工具，不进入普通 wheel、Plugin 或生产 broker。新工具单独固定 clean commit、文件摘要及验证证据；原安装 source commit/tree、wheel 摘要、native 来源和运行代码仍绑定原 plan，不能用恢复工具提交替换它们。

## 输入与一次状态

私有恢复计划固定原 preparation ID、原 plan/失败 receipt/命令记录摘要、原 reservation 目录身份、准确成功主组、现场 guest/boot/初始 user namespace、原 source/wheel/tool pins、唯一 recovery attempt ID、恢复工具来源、允许的准确接续点及新 envelope。字段严格校验，不接受任意命令或路径。

新状态为 `DECLARED → ATTESTED → RECOVERY_RESERVED → RECOVERING → RESOURCES_RECOVERED`。随后装配和运行状态独立记录。任何失败为 `INCOMPLETE`，不明结果为 `UNKNOWN`；保留 recovery attempt reservation，拒绝再次执行。原 preparation 的 `INCOMPLETE` 文件始终保持原字节。

恢复 reservation 是原准备证据目录内 create-only 的单独受保护子对象，按原 state 预算计费。写入前核对原目录 dev/inode、owner/mode、no-follow、无别名及固定成员集合；使用有限读取、create-only 写入、fsync，并保存全部旧文件摘要。恢复结束再次核对原字节未变。

## 副作用前鉴证

必须同时证明：

1. 原准确 plan 与暂存副本相同；原 receipt 为已知 `PREPARE_COMMAND_FAILED`，没有任何成功的 ordinary 或后续步骤回执。
2. 原 groupadd intent/result 对应计划名字与 GID，退出 0、完整双流且无捕获失败；现场按名字及 GID 查到同一无成员主组。
3. 原 useradd intent/result 对应计划账户，准确报配置项解析错误、退出 3、完整双流；用户名、UID 及其账户相关记录仍不存在，不接受未知副作用或其他失败原因。
4. 后续目录、安装、七个 quota project、实例级 manager 配置、专用父 slice、账本、装配声明、owner/handoff/运行 reservation 均未交付。同时检查原日志没有后续 intent，并实时检查对应系统对象；既有对象或不明事实一律拒绝。
5. guest、boot、namespace、文件系统、工具、source/wheel 与原计划相符；全部 Q1 保留对象摘要及旧 quota 限额保持；现余量能够容纳已有与剩余全部费用。
6. 原准备服务已实际结束，原 client 退出及双流材料可绑定；本次恢复服务独立于将停止的子树，使用新的原管理 envelope。

鉴证不接受宽泛“存在即复用”分支。唯一允许已存在的新增功能对象是由原成功命令绑定的主组及原准备记录/交付暂存。任何额外完成步骤改变该特定恢复合同，应保留并停止。

## 执行、装配与来源

首次恢复修改前保存准确恢复意图、鉴证结果和有限新 envelope。接续器不重放 groupadd；更正账户命令须采用现场已有工具支持的无登录、无 home/邮件等未声明对象的方式，并确认无附加组，之后才能执行原计划未交付步骤。每项副作用前追加 intent，之后保存真实身份、输出、退出与双流。

原 plan 不变。恢复实际事实形成独立 `RESOURCES_RECOVERED` 回执，引用原失败摘要、原 plan 摘要及恢复来源。装配只能消费完整鉴证的恢复回执；任何必要适配均须明确保留其恢复 provenance，不能改写原 receipt 为 `RESOURCES_PREPARED` 或把计划字段冒充实际观察。

原 broker operation、epoch、allocation、候选和静态配置绑定保持同一计划。只有证明运行 reservation、grant 和 issued/deadline 从未产生，才允许准备成功后的正常首次发行。之后不得重启替代 supervisor、重建 operation、重发 grant 或刷新任何已发行期限。

## 时限与失败保留

新 envelope 明确属于恢复管理调用；旧 envelope 不复活。外部管理与捕获上限 300 秒，guest service 上限 270 秒、停止上限 3 秒；其中鉴证、准备与装配上限 140 秒，尚未发行的原 Q2 owner 上限 120 秒。140 秒从 guest 恢复入口开始，在首次鉴证读取前固定绝对 issued/deadline。各层期限均在所属入口开始时固定、首次副作用前持久化，不能分步骤重新计时。原私有计划的 450 秒准备上限保持原字节，新 140 秒是单列批准的恢复上限。

每项命令受本次恢复 deadline 与原较小单命令限制共同约束；启动运行前必须为原 owner/target/phase、manager 调用、停止、EOF 和封存预留完整费用，不能仅用 140 + 120 小于 300 代替各嵌套绝对期限检查。guest 剩余窗口不足、外部捕获余量不足或任一期限已过即拒绝发行。所有已有与新增文件块/inode、输出及暂存统一计入原容量承诺。

外层实际退出与双流 EOF、子级停止和树空分别记录，不以任一子级成功字段代替。失败保留新旧全部对象，禁止自动回滚、重试、换 ID 或额外运行；不足即停止，不能扩大资源或改动系统依赖。
