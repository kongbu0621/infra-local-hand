# TC1准确冻结与TC2单次返回

**TC1完成；TC2已消费且失败；TC3/H01/Q4/H11未执行。**

范围 `LH-Q2-CORE-TEMPLATE-CONTINUATION-v1`，R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，准确A
`80c7c8eaeda0853317c679b31b0ed1f1ac13e49b`，独立C
`bb9b3c6e9b397121220c22515e4ef637d12c7297`；准确Owner B已登记。
本记录仅登记事实，不改变A、冻结源码或执行次数。

## 准确候选与执行前证据

执行D `d5b34316bc93b37442eb5db64ba265b965e68379`，tree
`593d90c6a26f936d76ba548d89dd09c760f0c46c`，已发布main并在TC2前冻结。
实际dispatcher SHA-256为
`b6c05ef78ddcce22cd33c2ecc6c2186705cc5cc9a3eff2dc9646d4c160f5d754`。
[实现审查](Q2_CORE_TEMPLATE_CONTINUATION_REVIEW_20261008.md)保存源码范围及本地首轮结果，
包括测试旧回执版本断言的失败和修正后37项通过；未把首次全组写成全绿。

[准确D首次CI 37657169056](https://github.com/kongbu0621/infra-local-hand/actions/runs/37657169056)
head_sha为上述D，run_attempt=1，三个job及两平台源码/独立安装步骤全部completed/success。
Linux **6525 passed / 89 skipped**，CI独立安装 **PASS / 94 checks / 292 commands**。
没有重跑CI。本机从准确detached源码构建的新wheel在独立venv同样 **PASS / 94 / 292**，
wheel及安装报告来源均为D；原现场runtime/wheel/projection/loader与安装保持。

TC1保护核验既有八输入、四旧核心批20件、诊断/容量各四件、三代失败维护十五件及
缺席名，实际生产解析器通过；固定user-data沿原pin核验。静态来源成员859件、
17506839 B、100目录，既有来源/归档关系通过。归档不含cloud-config的事实保留，
不把静态归档核对描述为覆盖该来源；其准确固定本机文件已在上述离线核对中验证。
维护源64353/59175 B均低于98304 B；三代预检在最大用量、大时钟样本下3915 B，低于4096 B。
TC1没有观察VM、发SSH、运行维护预检或生成真实核心包。
两段caller、准确CI/安装回执及其摘要已私有冻结，旧冻结副本没有修改。

## 唯一现场返回

`lhqjgrow-20261008a` 普通预检一次通过，以同原点、nonce、manifest和累计用量交接execute。
本次实际结果：

- `STOP_AND_RETAIN / GROWTH_REPORT_MISSING`，退出码3；marker已创建，SSH请求1。
- 开始状态只有 `CONSUMED`、`GUEST_QUIET`，business_cases=0。
- 已有guest stderr为 `INCOMPLETE / PRE_QUIESCENCE / GROWTH_SYSTEMCTL_NAMES`，
  `actions_started=[]`。已保留上下文指向system manager的show查询。
- 该错误类别来自Names字段校验；原输出没有具体Names值或被拒绝单元，不能断言
  是重复、格式还是正式Id成员关系导致，也不能据此声称模板/别名现场修复已全部通过。
- 原事件没有 `POWER_OFF_TOKEN`。本次没有关机、备份、镜像/文件系统增长或VM重启动作；
  journal扩容仍未完成。remote_exit保持UNKNOWN，不假造完整远端监督退出证明。

只保护读取并私有保留本次已产生的五件原件，与既有调用方输出、marker/manifest和流摘要
交叉核对。具体原因来自同次已有stderr，没有新查询、补采、重连、清理、恢复或重试。
本次08a原件及最小索引继续私有；本轮明确获准公开的是[旧07b五件索引](Q2_CORE_SYSTEMCTL_ORIGINALS_INDEX_20261008.md)。

TC2保持 **CONSUMED / FAILED**；旧06a/07a/07b及本次消费、原件、完整费用与UNKNOWN保留。
TC3条件未成立，原 `lhqcore-20261007a` 和H01→Q4→H11全部 **NOT_RUN**；
没有生成或发送真实核心包。私有gate已终止为 `TC2_CONSUMED_FAILED_TC3_NOT_RUN`，
执行前冻结证明和已消耗入口保留。不得重放任一caller，也不能用未发核心批绕过失败维护。
