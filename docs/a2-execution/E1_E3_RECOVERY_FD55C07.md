# E1–E3 中断交付恢复：fd55c07

记录日期：2026-09-23。

本记录恢复固定提交 `fd55c07e93f590afb14da3720f54ce2fcb872199` 已落仓的修复范围及对应 GitHub CI 结果，补齐中断后的可追溯交付说明。**这是已有提交与已有验证的恢复记录，不是第十一轮完整复核，不是新一次测试或实机验收。**

恢复时可确认：修复源码、19 个新增回归方法及准确提交的 CI 已保存；尚未恢复该轮原本地执行日志、修复前原始失败、独立审计材料和完整私有封存包。前一轮 `e349a83` 的证据继续只属于前一轮，不能转记给本提交。

## 1. 固定来源与核对方式

| 对象 | 准确身份 |
| --- | --- |
| 修复提交 | [`fd55c07e93f590afb14da3720f54ce2fcb872199`](https://github.com/kongbu0621/infra-local-hand/commit/fd55c07e93f590afb14da3720f54ce2fcb872199) |
| 父提交 | `7b8e2106d8072931349276585966d981e02305bb`，包含第十轮最终报告 |
| 修复 Git tree | `f977d9e04433a510f585a7efe28ebf6035484aeb` |
| 修复提交时间 | 2026-09-23 06:28:41 UTC |
| 对应 CI | [run 35826930309](https://github.com/kongbu0621/infra-local-hand/actions/runs/35826930309)，`push / main / attempt 1` |
| CI head | `fd55c07e93f590afb14da3720f54ce2fcb872199` |

本次只读核对了提交元数据与文件差异、该 tree 的完整路径目录（API 返回 `truncated=false`）、对应 workflow、CI job/step 状态、两个平台的 decoded job logs 及 artifact metadata。没有为本恢复记录重新运行源码测试、构建、安装或实机操作，也没有实施新一轮源码审计。

该提交只改动 15 个源码／测试文件：8 个源码文件、7 个测试文件，新增 865 行、删除 103 行，没有修改报告或状态文档。固定 tree 中复核报告最高仍为 [`E1_E3_RECHECK_10.md`](https://github.com/kongbu0621/infra-local-hand/blob/fd55c07e93f590afb14da3720f54ce2fcb872199/docs/a2-execution/E1_E3_RECHECK_10.md)，未发现第十一轮报告或与本提交对应的完整私有封存记录。这个结论只描述已核对的仓库内容，不声称私人存储中的材料已经丢失或不存在。

## 2. 已提交的修复范围

下表来自固定提交说明与 diff，解释已保存的实现变化；它不代替尚未恢复的修复前原始失败或独立复核证据。

| 源码位置 | 已提交变化 |
| --- | --- |
| `tools/local_hand/bounded_io.py`、`tools/local_hand/validate.py` | 可处理的中断、reader 启动异常或监视异常发生后，继续清理已拥有的子进程；保留中断／原异常含义，无法确认终止时保留不确定状态 |
| `tools/local_hand_jobs/broker.py` | 恢复后只在已有业务／核对结果、退出证明、冻结快照与事件顺序完整时允许第一次证据封存；保留通用恢复屏障和原预算，在意图形成及最后交付处重新检查当前条件 |
| `tools/local_hand_jobs/cli.py` | 极大整数超时参数先检查范围，保留 `INVALID_REQUEST`，避免整数转浮点异常逃逸 |
| `tools/local_hand_jobs/evidence_client.py` | 标准 ZIP 元数据分配前检查目录和成员预算，并通过同一 retained reader 验证归档 |
| `tools/local_hand_jobs/policy.py` | 检查路径祖先及输入文件所有者，收紧共享可写祖先的准入条件 |
| `tools/local_hand_jobs/resources.py` | authority registration 使用严格 JSON 解码；歧义或非法内容按 `IO_UNCERTAIN` 表达 |
| `tools/local_hand_jobs/runner.py` | 配额检查清理时保留原异常；`host.inspect` 准确记录业务已开始 |

提交 diff 新增 19 个公开测试方法，分布为：capture interrupt 4、jobs budget 3、jobs CLI 1、evidence client 6、policy 2、resources 1、runner 2。方法内子场景与全量测试有重叠，不叠加为额外通过数。

## 3. 准确提交的 CI 结果

CI run 于 2026-09-23 06:28:44 UTC 创建，06:39:10 UTC 更新为完成；`classify-change`、Linux 和 Windows 三个 job 均为 `success`。两个平台日志均记录准确 checkout SHA。

| 验证范围 | 对应 job | 原始日志中的结果 |
| --- | --- | --- |
| Linux 源码测试 | [107070632306](https://github.com/kongbu0621/infra-local-hand/actions/runs/35826930309/job/107070632306) | `761 passed, 1 skipped in 342.12s` |
| Windows S1 源码测试 | [107070632173](https://github.com/kongbu0621/infra-local-hand/actions/runs/35826930309/job/107070632173) | `211 passed, 136 skipped in 346.21s` |
| Linux 独立 wheel 安装态 | 同 Linux job | `PASS`；94 项检查、292 条命令 |
| Windows 独立 wheel 安装态 | 同 Windows job | `PASS`；10 项检查、10 条命令 |
| Python 编译 | 两平台 | 对应 compile step 均 `success` |
| Linux 独立 Plugin 构建 | 同 Linux job | 成功；状态为 `UNCONFIGURED_E4_REQUIRED` |

Linux 唯一跳过项的原始原因是：

```text
UNSUPPORTED real systemd/cgroup integration:
SUPERVISED_BOOTSTRAP_NOT_IMPLEMENTED;
no predelegated manager admission;
dedicated non-root account is required
```

Windows workflow 明确排除 `test_local_hand_jobs_*.py`、`test_local_hand_mcp_*.py` 和 `test_local_hand_plugin.py`；该结果只属于对应 S1／共享范围，不能声明 Windows A2 通过。新增的四个 capture interrupt 测试在 Windows 上以 `POSIX signal/process-group fixture; Windows deferred` 跳过。其余跳过原因仍按该次原始日志解释，不能将跳过数量视作已通过节点。

Linux workflow 安装冻结 MCP 依赖，源码 suite 包含适用的 MCP 测试；本次日志没有单列安装态 MCP 的独立通过数量。第十轮报告的安装态 MCP 结果不转记给本提交。安装态检查与源码 suite 也不相加；命令集合包含预期拒绝场景，`PASS` 不表示所有命令退出码均为零。

## 4. 已知构建与 CI artifact 元数据

Linux Plugin build 日志给出：

| 字段 | 值 |
| --- | --- |
| 来源提交 | `fd55c07e93f590afb14da3720f54ce2fcb872199` |
| 成员数 | 13 |
| 字节数 | 19218 |
| SHA-256 | `8035840668d81f2cf89815d28d71d5d9380391280c96ec1458e63132b2694454` |
| 连接状态 | `UNCONFIGURED_E4_REQUIRED` |

这证明该次构建记录绑定了准确源码，不证明已配置真实客户端连接或完成 E4 文件交付。

[GitHub artifact metadata](https://api.github.com/repos/kongbu0621/infra-local-hand/actions/runs/35826930309/artifacts) 返回以下两个归档，均绑定本 run 和准确 head；查询时 `expired=false`，标记到期时间均为 2026-12-22 06:28:44 UTC。

| Artifact | ID | 字节数 | API 报告的 SHA-256 |
| --- | --- | ---: | --- |
| `local-hand-Linux-35826930309-1` | `10735403596` | 620855 | `e71510253a6b4304adb91d0f8c660dfd65ef205981a4568a6a9f5e2bd9613ded` |
| `local-hand-Windows-35826930309-1` | `10735666412` | 214180 | `6b528a004b2e9fd0528e5237da4e388e5b48e7a169301c1a93d9719a27c5db48` |

本恢复记录没有下载这两个 ZIP 的二进制，没有解包或自行重算摘要；表中摘要准确标为 GitHub 返回的元数据。CI artifact 不等于原本地完整证据封存，也不保证永久保留。后续下载、核验或保存归档应另记实际结果，不能回写为本次已经完成。

## 5. 尚未恢复的材料与接续边界

| 材料或结论 | 本次能够确认的范围 |
| --- | --- |
| fd55 原本地完整源码测试 | 未恢复相应原日志；不从 Linux CI 数字推算本地数字 |
| 修复前失败及中间候选 | 未恢复原始失败、候选快照和命令证据；不依据最终 diff 合成历史失败 |
| 独立审计 | 未恢复该轮准确候选的独立审计记录；不声明完整复核已经收口 |
| 完整私有证据包／外 seal | 未恢复可核验的准确包名、成员清单及摘要；不沿用第十轮封存包 |
| 第十轮封存材料 | 继续准确绑定 `e349a83fde7ee1901d966303aba135b171d3d18d`，与本提交分别保存 |

fd55 的提交说明明确保留 production deployment guards；该提交没有补齐受监督启动准备和 NAS 硬配额适配。该准确 CI 仍跳过真实 systemd/cgroup 验收，Plugin 仍未配置 E4 连接。固定提交中的 [`IMPLEMENTATION_STATUS.md`](https://github.com/kongbu0621/infra-local-hand/blob/fd55c07e93f590afb14da3720f54ce2fcb872199/docs/a2-execution/IMPLEMENTATION_STATUS.md) 因而仍记录 `E1_INCOMPLETE_E3_BLOCKED_NOT_DEPLOYABLE`，E4、E5／S2、E6 未完成。以上是 fd55 的历史状态；后续功能实现及验收必须绑定后续准确提交和实际证据，不能用本记录提前宣布完成。

接续保持 [AGENTS.md](../../AGENTS.md) 已记录的 E1–E3 授权范围和既有来源链；本记录不改变设计基线、开工范围、生产部署状态或任何 Gate。恢复原私人材料时继续保留其真实来源和缺失项；若材料无法恢复，可在后续准确源码上开展必要的新验证，但只能记为新的验证，不能代替或伪造历史记录。公开仓库仅保存本脱敏结论与公开 CI 链接，原始私人日志、主机配置和凭据不随之公开。
