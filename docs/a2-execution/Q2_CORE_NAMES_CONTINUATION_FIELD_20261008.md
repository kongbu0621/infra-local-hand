# NC1准确冻结与NC2单次返回

**NC1完成；NC2已消费且失败；NC3/H01/Q4/H11未执行。journal扩容未完成。**

范围 `LH-Q2-CORE-NAMES-CONTINUATION-v1`，R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，准确A
`68cae882e3b831aaa191e7a877278ccf6ba10e2b`，独立C
`eba5023b13e42d4610533b7e7c4eede3ebd658db`。
[准确Owner B](../governance/Q2_CORE_NAMES_CONTINUATION_OWNER_DECISION.md)先于实现登记；
C只含B与CLOSED记录，未合并实现。A三文档的原字节及历史OPEN标签保持。
本记录只登记验证与实际结果，不改变授权、冻结源码或执行次数。

## 准确候选及执行前证据

执行D `dc538b9034f00c635344defae57b7054319c2184` 是C的直接子提交，tree
`f24d649fef2a8f0414d031c19987644c71971a49`，已发布main并在NC2前冻结。
dispatcher SHA-256为 `dab3da262854f5da53ed19e6561c881644ccee693fe77f20b8970d5b4c02ff26`。
[实现审查](Q2_CORE_NAMES_CONTINUATION_REVIEW_20261008.md)保留全部源码范围、
首次本地测试的八项测试构造失败及修正后精确复核，不把首轮描述为全绿。

[准确D首次CI 37714259488](https://github.com/kongbu0621/infra-local-hand/actions/runs/37714259488)
head_sha为上述D，run_attempt=1，三个job及两平台源码、独立安装步骤全部completed/success。
Linux **6740 passed / 89 skipped**；CI独立安装 **PASS / 94 checks / 292 commands**。
没有重跑CI。本机从准确detached D构建并在独立venv安装的候选同样 **PASS / 94 / 292**，
wheel元数据及安装报告来源均为D；原现场安装、runtime/wheel/projection/loader不变。

NC1保护核验既有八输入、四旧核心批20件、诊断/容量各四件、四代失败维护20件及16个
缺席名，生产解析器通过。固定user-data沿既有整文件pin验证；历史归档缺少cloud-config
的事实保留，不把归档核对说成覆盖该来源。静态成员859件、17507887 B、100目录，
原来源/归档/dispatcher允许值关系通过，没有生成真实核心包。

两维护源65610/60268 B低于各98304 B；固定四代真实pins、最大计量和20位钟构造的
短预检为708 B，4096 B上限保持。manifest保存完整四代历史，短预检仅摘要绑定重复
resume，execute重新构造并核对完整manifest、历史、nonce、原钟和累计用量。
五代维护完整义务6480 MiB/1850 inodes，含核心6544 MiB/1866；原单次预算和期限保持。
准确CI、安装、静态输入、两段caller及摘要于NC2前私有冻结。

## 唯一现场返回

`lhqjgrow-20261008b` 普通预检一次通过，同原点、nonce、manifest及累计用量进入execute。

- 返回 `STOP_AND_RETAIN / GROWTH_REPORT_MISSING`，退出码3；marker已创建，SSH请求1。
- 开始状态只有 `CONSUMED`、`GUEST_QUIET`，business_cases=0。
- 同次已有guest stderr为 `INCOMPLETE / PRE_QUIESCENCE / GROWTH_SYSTEMCTL_FORMAT`，
  `actions_started=[]`，其诊断上下文指向system manager的show查询。
- 准确D中该错误来自show响应块的键值行格式或键唯一性检查。保留输出没有原响应块、
  具体行或具体失败子条件，不能确定是缺少分隔符、重复键或其底层原因，也不能据此
  声称Names修复已完成全现场验证。没有追加查询取证。
- 原事件没有 `POWER_OFF_TOKEN`。本次没有关机、备份、镜像/文件系统增长或VM重启动作；
  journal扩容未完成。remote_exit仍为UNKNOWN，不假造完整远端监督退出证明。

仅保护读取并私有保留本次已产生的五件原件，核对调用方返回、marker/manifest、receipt、
事件及流摘要。没有新查询、补采、重连、重试、清理、恢复或支线工作。
本次08b原件及最小索引保持私有；获准公开的[旧08a五件最小索引](Q2_CORE_TEMPLATE_ORIGINALS_INDEX_20261008.md)
已经发布，范围仅basename/bytes/SHA-256，不包含原正文、路径或机器环境。

NC2为 **CONSUMED / FAILED**；旧06a/07a/07b/08a和本次的消费、原件、完整费用及UNKNOWN
全部保留。NC3条件未成立，原 `lhqcore-20261007a` 和H01→Q4→H11均 **NOT_RUN**，
没有生成或发送真实核心包。私有gate已终止为 `NC2_CONSUMED_FAILED_NC3_NOT_RUN`，
执行前冻结证明、消费记录及caller保持。不得重放任何旧或本次caller，不能用未发核心批
绕过失败维护；本轮不自动申请另一窗口。
