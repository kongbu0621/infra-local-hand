# Q2 固定本地来源补证：实现与交付复核

2026-09-28 +08。准确 A `b8b9ec3da3de43b72e4e17416ea6633494d50c1d` 已获
[Owner 决定](../governance/Q2_LOCAL_SOURCE_EVIDENCE_OWNER_DECISION.md)；独立关闭 C 为
`8e7545199bde66583e1d643656dece867ab1dbda`，本实现 D 为
`411a9f054d0ee85c3e82296a1fdd3a9ed4ae6239`，tree
`21773876ef321eb70fdfd9dc24cbeed881efd2ef`。首次实现 `4c1285a3` 直接以 C 为父，
新增三个专用模块和三个测试文件；后续 `317b09f3`、最终 D 修正测试目录及 CI 准备。
三个生产模块自首次实现后逐字不变；原共享三个模块、旧十二份及新三份冻结文档字节保持。

## 已实现的限定行为

| 合同 | 实现与证据 |
| --- | --- |
| 固定来源与目标 | P/M/T 原字节长度/摘要先核验，再严格派生7个相邻文件与4份控制文件；无调用者目标覆盖，准确私有原件离线派生为11项 |
| 普通身份与保护 | 捕获真实/有效/保存uid/gid和groups并持续检查；held祖先/名称/fd、ACL及NOATIME保持，权限或保护失败不降级 |
| 有界单次读取 | 普通文件内容仅一次加最多1字节EOF/超长检测，元数据复核不重读；有效上限10,490,352，实际read上限10,490,363 bytes |
| 差异语义 | 缺失、长度改变、稳定等长摘要差异按逐项规则留存；来源摘要与实测摘要分开，未读或不稳定对象不报告实测摘要，四raw仅完整匹配且稳定后返回 |
| 时间与资源 | 接收前原双钟持续覆盖输入/校验/观察，准备140秒、总300秒及原2秒双钟差额保护；startup+frame共用16MiB，stdout+stderr共用2MiB |
| 内核与FS事实 | 仅两次boot、一次自身mountinfo，实际内核read上限1,048,707；两父目录metadata/statvfs/flags，明确不支持如实保留，不推导分配峰值或durability通过 |
| 准确RAM交付 | 包工具、P/M/T及新旧R/A/C与D/tree的Git证明在工具首次执行前核验；只允许离线校验或固定本地观察，工具闭包为六模块 |
| 有界失败输出 | 最终输出计数包含交付字段；超限时保留完成数量与实际read，明确原文已省略，不将省略原文计为已交付；不生成第二份补全输出 |

上述代码不执行wrapper、carrier或控制脚本，不连接guest，不创建marker，不消费批次。
K4五树不重扫，旧42与新7不拼成同刻完整49；结果只能为OBSERVED_PARTIAL或
LOCAL_SOURCE_EVIDENCE_BLOCKED，各项业务许可始终false。

## 本地验证

- 最近一次本地相关六组：**211 PASS / 3 SKIP**，1.81秒。新增三组为136 PASS / 1 SKIP；
  其余75 PASS / 2 SKIP来自未修改的固定内核、held IO和RAM工具加载组件。
  此次运行后仅更改 CI fixture 位置字面量及测试helper说明文字；生产模块和可执行测试逻辑
  未变，未宣称在最终 D 逐字重跑本地六组。最终 D 的准确远端 CI 单独登记如下。
- 三项SKIP是本工作容器只有root映射，无法取得实际普通身份或映射/chown测试UID。
  不能把这些结果当成原普通身份通过，亦未以mock取代其真实验证要求。
- 新代码使用开发真实文件/PTY及明确合成来源、身份或内核事实做边界测试；不冒充原host。
- Python3.12.14 / pytest8.4.2隔离环境；三个新模块及三个测试均编译通过，并通过
  Python3.10语法检查。旧开发环境未修改。
- 独立审查修正了最终输出计量、失败范围保留、双钟差额、来源/实测摘要分离和普通身份
  CI fixture关系。源码最终没有未关闭的必须修正项。

这不是此前全Q2的942项回归重跑，也不是全仓或Q2验收通过。

## 准确交付及普通身份验证

准确 D 的私有 RAM 包为 **4,107,619 bytes**，SHA-256
`b97112107193000ae36266b7d2179167fc60dcb38ecf8d4d62ff7dcb0c2dcdda`。
23个成员、展开5,950,952 bytes；startup 27,191 bytes、input frame 5,487,647 bytes，
合计 **5,514,838 bytes**。同 D 两次独立组包逐字一致；离线 Git/权限来源绑定、
六工具逐 Git 字节、启动命令/输入帧 roundtrip 与11个目标派生均通过独立复核。
独立离线复跑封禁现场文件 IO，仍得到 OFFLINE_CHECK_PASS。

准确包的开发真实 PTY 返回完整6,883 bytes JSON，普通身份门槛按预期提前阻断
`LOCAL_SOURCE_ORDINARY_IDENTITY_REQUIRED`；11目标均未尝试，普通文件及内核read均0，
终端状态恢复、载荷未回显、工作目录无写入。此项仅证明准确传输与提前拒绝路径。

首次实现 D `4c1285a3` 的 [CI 36391489578](https://github.com/kongbu0621/infra-local-hand/actions/runs/36391489578)
为 Linux 55 FAILED / 2257 PASS / 36 SKIP，较前一 v1 修复多34个 observer失败及1个普通身份
跳过。多项错误明确为 `LOCAL_SOURCE_ACL_PRESENT`，后续观察未到达；不能将这些结果当成阳性。
前一 v1 CI 的21个失败及35个skip和各自已显示原因保持。Windows原6个收集错误不变，
新增2个明确Linux-only模块skip，总9个；收集被中断不证明平台无关contract测试已执行。

中间修复 `317b09f3` 的 [CI 36392913200](https://github.com/kongbu0621/infra-local-hand/actions/runs/36392913200)
在全新 `/opt` fixture子目录上再次检测到ACL，准备阶段即失败，Linux源码测试未执行；
该日志未给出ACL类型，不能断定其具体继承来源。原始失败、准确中间源码及中间开发包均保留。

最终修复把测试用独立随机目录放在文件系统根下，仅准备新目录并赋予runner所有权；
既有目录权限和ACL不改，测试/采集器均保持真实普通身份。设置测试专用父目录后，
身份及完整保护链失败一律FAIL，无fallback或SKIP；生产入口不接受此环境变量。
本地明确配置加root验证为预期1 FAILED，普通身份不可用不再被配置分支跳过。

最终 D 的 [CI 36393186487](https://github.com/kongbu0621/infra-local-hand/actions/runs/36393186487)
已完成。Linux **21 FAILED / 2294 PASS / 35 SKIP**（454.28秒）；与准确前一 v1 修复
`14d19f1f` 比，旧21失败及35跳过节点和日志中已显示原因不变，新增测试 **137 PASS**，
三个新增模块无失败、无跳过。首次 D 的34个新增失败及普通身份额外跳过均消除。
Windows仍为原6项收集错误、9 SKIP，含2个明确Linux-only模块跳过，无新增收集错误。
全仓 CI 因这些原有问题仍失败，后续wheel/安装步骤因源码测试失败被跳过；不据此称完整构建通过。

[准确 Linux job](https://github.com/kongbu0621/infra-local-hand/actions/runs/36393186487/job/108833454373)
实际pytest输出包含 `LOCAL_SOURCE_ORDINARY identity=ordinary noatime=PASS ancestor_acl=PASS metadata=STABLE`，
对应普通身份用例无失败或跳过。这证明 CI 隔离文件的真实普通身份、NOATIME、完整祖先ACL
和元数据稳定检查通过；不是原 host 证明，也不证明普通身份writer或完整Q2准入。

源码、交付计量与 CI 的脱敏机器记录见
[verification.json](evidence/q2-local-source-20260928/verification.json)。私有载荷、路径、
四控制文件及开发原始回执未发布到公开仓库。原 host 尚未执行；L5 回执与 L6 实际原文
复核待后续真实返回。现处于 L4 交付就绪／待 L5，不把 Gate 关闭等同于 L6 或 Q2 完成。

## 后续边界

本scope批准仍有效，范围内实现/验证/准确交付不再逐项请求批准。L5只安排一次原
PRO6000普通终端调用，用户回传已有结果后先做收件核对，不自动重试；同范围再次
观察须Owner明确发起，但不重复批准相同A。

本scope不关闭普通身份writer、H07首次远端监督、完整账单/原生审计费用、wrapper
历史执行来源、FS分配峰值/持久资格或Q2/Q3。原单次新 startup batch 仍 NOT ISSUED 且未消费；
旧批次已消费失败及历史 INCOMPLETE 保留。
`allow_run`、`allow_consume`、Q2/Q3和production supported均false。
