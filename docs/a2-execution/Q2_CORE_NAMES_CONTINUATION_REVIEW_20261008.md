# NC1：有界短预检与四代历史实现审查

准确批准A `68cae882e3b831aaa191e7a877278ccf6ba10e2b`，独立C
`eba5023b13e42d4610533b7e7c4eede3ebd658db`，R保持。准确Owner B见
[决定](../governance/Q2_CORE_NAMES_CONTINUATION_OWNER_DECISION.md)。本实现承接C，
A三文件原字节及历史OPEN标签保持；NC2/NC3执行须等待后述冻结条件。

## 实际变更

旧08a严格按原template manifest/receipt v5、原R/A/C/D及三代嵌套resume验证。
四代二十件原件及十六缺席名进入原保护读取、消费前同FD重读和核心读取；跨集合inode
去重、元数据及原件/流/事件关系保持。公开仅获批[旧08a五件索引](Q2_CORE_TEMPLATE_ORIGINALS_INDEX_20261008.md)，
其值已与私有附件及保留副本再次核对；原文、路径、环境和诊断未公开。

新08b manifest/receipt v6仍保存完整四代resume。短预检v5仅以SHA-256替换重复resume，
取既有canonical含LF的完整历史摘要。构造器显式要求已验证的manifest.resume；解析器
严格对照候选固定历史；execute同时重建完整manifest、核对D、nonce、原钟、manifest
和历史摘要，原计量衔接不变。拒绝旧v1–v4及额外字段，不以摘要代替原件和语义验证。

新R/A/C绑定准确来源；维护入口核对A/C树、A三文件在A/C/D的字节、B在C/D的字节及
独立C祖先，完整freezer同样验证。原所有历史授权继续保留。两维护源65610/60268 B，
低于98304 B；四代真实pins、最大计量及20位钟样本短预检708 B，原4096 B上限不变。

完整核心projection更新transition v5，reconciliation/history v9、host-capacity v8；
host和独立guest保留完整四代验证。五代完整维护义务6480 MiB/1850 inodes，含核心
6544 MiB/1866（6861881344 B），各120 CPU-s、旧UNKNOWN及所有原单次限额不变。
当前dispatcher SHA-256为 `dab3da262854f5da53ed19e6561c881644ccee693fe77f20b8970d5b4c02ff26`。
原runtime/wheel/projection/loader、安装、SSH文法和原核心H01→Q4→H11语义保持。

## 本地源码证据

首个相关组580 passed。维护/核心全部受影响组首次 **2688 passed / 47 skipped / 8 failed**。
八项失败均来自新增拒绝测试将所有getrlimit结果伪造为无限，触发finally恢复NOFILE硬限
时的测试错误。删除该伪造，保留真实限制，精确复核这八项后 **8 passed**；没有为此
改产品代码或放宽限制。原始失败输出和复核结果保留，不把首次全组描述为全绿。

新增100项覆盖08a原三代嵌套关系、四代重哈希篡改、规范含LF摘要、4096/4097入口边界、
旧版本/字段/授权/原钟/计量拒绝及无现场读取、完整核心双方投影拒绝、准确A/B/C来源。
既有保护读取及双方历史反例扩展至第四代；完整原动作合成路径和旧全部检查继续通过。
跳过按实际环境保留，不计PASS。实现期间一次语法检查误用Python3.10读取原有3.12
dispatcher语法而报错；项目及正式源码测试使用要求的Python3.12，该错误未引起源码修改。
所有旧64位hex来源pin仍保留，仅当前dispatcher发布allowlist替换为上述审查值。

## 发布及冻结前置

本记录随实现提交，尚不宣称准确新D的CI、独立安装、真实保留输入和静态完整构包检查
已经完成。新维护/条件核心caller已私有准备但未调用，旧caller及冻结副本不改。
下一步须新D发布、首次准确CI、独立installed与既有八输入/四旧核心/四代维护原件核对，
原包及全部大小上限通过，再冻结同一D的两段caller。此前NC2/NC3均NOT_RUN。
无新现场查询、维护预检、VM观察、SSH或真实核心包；失败不重试、不补采、不清理。

上述为实现提交时的状态。随后准确D验证、发布及冻结完成，唯一NC2窗口已消费且失败，
NC3/H01/Q4/H11未执行；详见[准确冻结与单次现场返回](Q2_CORE_NAMES_CONTINUATION_FIELD_20261008.md)。

## systemctl 多命令属性解析修复

08b只保留 `GROWTH_SYSTEMCTL_FORMAT`，没有具体响应行或失败子条件。本次离线审查
确认一个独立、可复现的解析缺陷，不能据此补造08b现场原因或宣称维护已成功。

官方 systemd v255 [systemctl-show.c](https://github.com/systemd/systemd/blob/v255/src/systemctl/systemctl-show.c)
的 Exec 数组分支逐条反序列化并调用 `bus_print_property_valuef`；
[bus-print-properties.c](https://github.com/systemd/systemd/blob/v255/src/shared/bus-print-properties.c)
每次输出独立的 `name=value` 行。因此合法多条 ExecStartPre、ExecStartPost、ExecStop、
ExecStopPost、ExecReload，以及 oneshot 多条 ExecStart 会重复同一个键。旧代码全局
要求键唯一，必然以 FORMAT 拒绝。这与 Names 显示解码是不同的现有解析缺陷。

修复仅允许上述六个既有 Exec 属性多行，按原顺序以 LF 聚合全部值，继续用原字符串
接口进入身份/别名一致性、属性摘要、受保护根、间接启动及 domain 动作检查。
不采用覆盖前项或只保留末项；相同命令出现多次也保留次数。所有标量和未知键仍禁止
重复；未知字段集合、Id、Names、覆盖、返回码、EOF、stderr 和各资源限额检查保持。

同次 FORMAT 失败保留 `missing_equals` 或 `duplicate_scalar`、响应块序号、行号、
已知属性名（未知为null）、首次出现行号、失败行字节数与SHA-256；仅已有且语法有效
的 Id 进入 unit。诊断不含属性值、未知键正文或命令参数，不追加查询/连接/重试。
其余未验证显示形式仍严格拒绝，避免以宽松解析掩盖不完整响应。

最终相关组 **1034 passed / 5 skipped**；新增多命令属性测试 **100 passed、无跳过**。
包含本机v255原生 `bus_print_property_value` 纯格式输出、六属性的完整保序/重复次数、
首中末条目的受保护路径/间接启动/domain拒绝、alias中间条目冲突、属性哈希覆盖全部
成员及次序，以及第二响应块具体格式错误和有界无参数诊断。原生测试未连接管理器或总线。
五项跳过分别为既有PID/proc身份一项、缺少qcow2/ext4工具一项和不允许私有Unix socket
的三项模板测试。首次相关组为933 passed / 5 skipped / 1 failed：旧测试以object.__new__
构造对象而缺少真实ctl会初始化的context；只补齐该测试上下文，未为测试放宽生产检查。

独立审查以1 MiB合成响应、248 B单元名和超长坏行检查诊断：context652 B、完整failure
1170 B，无命令内容。host源65610 B、guest源61275 B，均低于原98304 B上限。
本段是源码与隔离验证证据；候选发布后的准确CI、独立安装和现场结果须分别核对。

现场08b以及之前所有消费、原件和UNKNOWN保持；已批准A三文档、固定授权与冻结
caller保持。本次只修复阻挡核心链的现有解析实现，不建立新窗口或新增分支功能。
