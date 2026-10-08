# 08d 未声明业务单元：本地原件离线核对

日期：2026-10-08。承接[诊断修复交接](Q2_CORE_GUEST_STARTUP_CONTINUATION_REVIEW_20261008.md#未声明业务引用的同次诊断补齐)。
本轮完成已留存输入的离线交叉核对；**现场原因仍未确定，journal 维护及 H01/Q4/H11 未完成**。
没有修改运行代码、固定候选、声明清单或判断条件，没有新现场查询或窗口。

## 准确来源与验证

本地已快进至诊断提交 `fd6f2a6c4d07622b4ba7daf7237fd0212369d0f5`。
其[准确 CI 37741778828](https://github.com/kongbu0621/infra-local-hand/actions/runs/37741778828)
已完成，分类与 Linux/Windows 两项语义作业均 success。本地同次诊断定向测试
**48 passed**。首次误用不含 pytest 的交付 runtime 环境，未运行测试；改用已有开发
测试环境后通过，两个日志均保留。此验证不代表现场修复或再次准入。

08d 的实际执行候选仍为 `341796561a6aaa6f95779f438b57d958a1fd5954`，
不是后续诊断提交。使用 O_NOATIME/O_NOFOLLOW 的有界稳定读取核对已经保留的五件原件，
与原 execution-result 和 terminal gate 的摘要关系相符。consumed 中 manifest 与原
普通预检一致；其 inventory 摘要与 pre_description 中对应清单一致。新 08d 原文、
精确单元名、主机路径及五件索引仍私有，本文件不公开这些内容。

## 清单核对结果

从固定原计划、retry preparation 和六代历史输入纯计算重建清单：

| 核对项 | 结果 |
| --- | --- |
| expected 服务名称 | 18 个，与冻结清单逐项一致 |
| domain 单元 | 6 个，与冻结清单一致 |
| protected roots / essential paths | 230 / 180，与冻结清单一致 |
| 原 boot 绑定 | 与冻结 descriptor 一致 |
| 四个已知 core carrier 的 control_group | 原生成值为 null；冻结记录的差额仅限原 HELLO 调整位置，本轮不把历史值重认作当前状态 |
| 失败报告中的请求单元名 | 不在冻结 expected/domain 集合中 |

该名称形式与仓库 Q1 quota 查询单元的 `lhq-<64 位摘要>.service` 生成方式相符；
**名称形式不能证明实际来源、canonical Id、历史请求或业务归属**。冻结 expected 集合
没有这种 Q1 查询单元，选定 plan/retry/history 文档中也没有这种名称值。因此本轮
没有复现“已有单元字段被解析器漏读”的确定缺陷，不能直接追加未知名称。

核对了七份固定摘要的历史归档：六份后续 evidence ZIP 和原 guest raw TAR。
归档没有命中报告中的完整名称，成员目录也不含旧 Q1 配置、查询 intent、unit 或
drop-in 原文；没有遗漏的嵌套压缩包。此外，仅在本地已有的两份 management/inventory
ZIP 与三份 recovery/retry JSON.GZ 中作了有界检索，包括 30 个明确编码的 base64 值，
也未命中。这五份额外文件的本次摘要仅用于私有审阅定位，没有将其升级为新的历史
权威输入。该结论限于已检查材料，不声称 guest 上从未存在这些记录。

## 尚缺的准确证据与停止边界

08d 旧 stderr 仅有 manager 和请求单元名，没有成功的 `systemctl show` 属性内容、
实际 canonical Id、命中属性、保护根序号或匹配位置。新诊断不能回填旧响应。
当前检查材料也没有能绑定该名称的旧 Q1 query intent/原 ticket 和相应配置。

若已有原件可供后续离线审查，需要下列任一充分关系，而不是新状态的猜测：

- 当时该单元的完整固定 SHOW 属性响应，包含 Id/Names 及命中属性，能与原保护根比较。
- 能从 manifest_digest、slot_ref、generation、request_id、allocation_digest、
  execution_id、phase 重算查询单元名的原 intent/票据，以及该请求的原配置、启动参数
  或已留存 unit/drop-in 内容。历史身份关系仍不能替代本次未保存的实际属性或静止证明。

目前无法区分真实业务引用未声明与相似子串匹配，也无法证明存在活动 writer。保留
原拒绝条件，不添加白名单、不以名称前缀豁免。没有复用旧 caller、SSH、补采、安装、
关机、备份、扩容、重启或清理；私有 gate 仍为
`GS2_CONSUMED_FAILED_GS3_NOT_RUN`，七次维护消耗及全部 UNKNOWN 保持。
本轮只关闭“核对现有本地材料”的交接项，不关闭现场问题，不生成新 A/B/C 或执行许可。
