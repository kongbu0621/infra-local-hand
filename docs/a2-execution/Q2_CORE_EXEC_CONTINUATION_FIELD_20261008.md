# EX1准确冻结与EX2单次返回

**EX1完成；EX2已消费且失败；EX3/H01/Q4/H11未执行。journal扩容未完成。**

范围 `LH-Q2-CORE-EXEC-CONTINUATION-v1`，R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，准确A
`5b14123206ced8117374d3fd2ef84b9f38784db3`，独立C
`987c77f6eb16e7ca41d8b1d4ccd7f89faf418d32`。
[准确Owner B](../governance/Q2_CORE_EXEC_CONTINUATION_OWNER_DECISION.md)先于实现登记；
C只含B与CLOSED记录，未合并实现。A三文档原字节和历史OPEN标签保持。
本记录只登记验证及实际结果，不修改授权、冻结源码或执行次数。

## 准确候选及执行前证据

执行D `064bdd614db4224c8c7e9d3b011af90622c11066` 是C的直接子提交，tree
`f8bbaf30c7bead15d0a3f287a1f131e6ca5f6013`，已发布main并在EX2前冻结。
dispatcher SHA-256为 `192ac9ebfd024e970498b2e4a5e7b72a2d62625403510f21812e03f5ff266747`。
[实现审查](Q2_CORE_EXEC_CONTINUATION_REVIEW_20261008.md)记录源码范围及首次本地
2914 passed / 48 skipped / 1 failed：唯一失败为旧测试仍断言四代历史，修正该断言后
精确复核1 passed。首轮失败保留，不把首次全组描述为全绿。

[准确D首次CI 37722136695](https://github.com/kongbu0621/infra-local-hand/actions/runs/37722136695)
head_sha为上述D，run_attempt=1；三个job及两平台源码、独立安装步骤全部completed/success。
Linux **6960 passed / 89 skipped**；CI独立安装 **PASS / 94 checks / 292 commands**。
没有重跑CI。本机从准确detached D构建、独立venv安装的候选也为 **PASS / 94 / 292**；
wheel元数据和安装报告来源均为D。原现场安装、runtime/wheel/projection/loader保持。

EX1保护核验既有八输入、四旧核心批20件、诊断/容量各四件、五代失败维护25件及20个
缺席名，生产解析器通过。固定user-data沿原整文件pin验证；历史归档缺少cloud-config
的事实保留，不把归档核对说成覆盖该来源。静态成员859件、17508915 B、100目录，
原来源/归档/dispatcher允许值关系通过；没有生成真实核心包。

两维护源66421/61275 B低于各98304 B；五代真实pins、最大计量和20位钟构造的短预检
为708 B，原4096 B上限保持。完整五代历史仍在manifest中，短预检摘要绑定实际resume，
execute重新构造并核对完整manifest、历史、nonce、原钟和累计用量。
六代维护完整义务7776 MiB/2220 inodes，含核心7840 MiB/2236；每代120 CPU-s及全部
原单次预算、900s/780s维护期限保持。准确CI、安装、静态输入和两段caller在EX2前冻结。

## 唯一现场返回

`lhqjgrow-20261008c` 普通预检一次通过，同原点、nonce、manifest及累计用量进入execute。

- 返回 `STOP_AND_RETAIN / GROWTH_REPORT_MISSING`，退出码3；marker已创建，SSH请求1。
- 开始状态只有 `CONSUMED`、`GUEST_QUIET`，business_cases=0。
- 同次已有guest stderr为 `INCOMPLETE / PRE_QUIESCENCE / GROWTH_INDIRECT_STARTUP_UNVERIFIED`，
  `actions_started=[]`；诊断指向系统manager的定时任务类间接启动入口。
- 对照准确D源码，该路径在已启用、未列入已声明业务或域单元的启动命令中匹配到间接
  启动类别后拒绝。它没有证明某项定时任务正在运行、写入镜像或造成数据冲突，也不
  构成全部启动检查通过。没有追加查询、停服务或更改检查规则。
- 原事件没有 `POWER_OFF_TOKEN`。本次没有关机、备份、镜像/文件系统增长或VM重启动作；
  journal扩容未完成。remote_exit仍为UNKNOWN，不补造独立远端监督退出证明。

仅沿原保护读取核对并私有保留本次已经产生的五件原件，验证调用方返回、marker/manifest、
receipt、事件及流摘要关系。没有新现场查询、补采、重连、重试、清理、恢复或支线工作。
本次08c原件及最小索引保持私有；获准公开的[旧08b五件最小索引](Q2_CORE_NAMES_ORIGINALS_INDEX_20261008.md)
已发布，公开范围仅basename/bytes/SHA-256，不包含原正文、路径或机器环境。

EX2为 **CONSUMED / FAILED**；旧06a/07a/07b/08a/08b与本次的消费、原件、完整费用和
UNKNOWN全部保留。EX3条件未成立，原 `lhqcore-20261007a` 及H01→Q4→H11均 **NOT_RUN**，
没有生成或发送真实核心包。私有gate已终止为 `EX2_CONSUMED_FAILED_EX3_NOT_RUN`；
执行前冻结证明、消费记录及caller保持。不得重放本次或任何旧caller，也不能用未发
核心批绕过维护失败；本轮不自动申请另一窗口。
