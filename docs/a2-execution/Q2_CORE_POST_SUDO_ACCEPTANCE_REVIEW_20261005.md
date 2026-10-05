# sudo 修复后单次核心验收实现与验证

2026-10-05 +08:00。范围 `LH-Q2-CORE-POST-SUDO-ACCEPTANCE-v1`，仅 S1–S3。
最终检查点：S1 已交付，最终发行 D 的 S2 全部通过后执行了 S3 的唯一 05b 请求。
05b marker/request 均已消费；在准入阶段返回 `CORE_ADMIT_SSHD_GRAMMAR`，没有业务结果包。
真实业务执行及结果回收在原 receipt 中均为 UNKNOWN；H01/Q4/H11 无 verdict，不是核心验收 PASS。
五件失败 capture 已保留，发行 allowlist 再次关闭；本范围以保留失败结束，不重试、重连或清理。
以下未发出/待验证表述是已被最终章节取代的历史检查点，不是新的执行机会。

## 授权与固定身份

R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 已直接读取并核对原 SHA-256。
准确 A `f9ba6fbc2fa983c46322a00f3385af172fed7cb4` 三文档字节不变。
[Owner 逐字决定](../governance/Q2_CORE_POST_SUDO_ACCEPTANCE_OWNER_DECISION.md)及根 Gate
构成独立 bookkeeping-only C `0c63e733b166f8f9539fd821db621b331a3ede61`，tree
`569083f1fe775c918983a88a963aebf810aa1d27`。实现提交单独以 C 为父，不合并 C/D。

新 session/carrier/install/staging、三 case UUID/preparation/controller、21 project IDs、
包与六个 capture 名字全部采用 A 的 05b 固定表。现场 candidate/wheel/projection 保持 A 原值。
新的 A/B/C 树、祖先和文档/决定摘要加入 offline freeze；原所有批准链不替换。

## S1 实现

- 两个原 prior/v2 固定 profile，reconciliation/v3 与 historical-obligations/v3 恰两项有序数组。
  host 和独立 guest 消费者逐项核验原 bytes、各自 D/包/HELLO/传输/receipt，不借第一批零 BIND 解释第二批。
- 两旧 A/B 顺序为 03a A → 05a A → 原容量/manager → 03a B → 05a B。
  两 observer 持有 fd 到全部 B 与最终 name/parent 复核；未新增第五次 SHOW。
  修复管理 helper 的通用 argv 防重放与必要 A/B 重复 argv 冲突：仅固定四个观察槽可各执行一次，
  第一次失败保留槽并停止，不能前进或重入；原 wait4/双 EOF/CPU/输出限制保留。
- 两旧每项全额 276 MiB/16512、2090 CPU-s 与逐设备保守重复保持，另加新批及更早 guest 义务。
  新旧三个 HELLO 各 1 GiB/128，前置上界仅三 carrier 合 3 GiB/384，不是整机可用量或排他预留；
  静止通过后新批原 2624 MiB/1160 不变。SHOW helper 继承新 carrier，使用原 usage collector；
  不计成 quota native child、不新增 unit 或整机探针。
- 原 pre-marker 单次容量条件改为 192 MiB/48、三行固定 host capture 承诺，返回条件/v2
  绑定有序双 prior 摘要、D、原 writer/anchor/window，并由 live finalizer 再验；仍只六文件。
  更早 host 历史 UNKNOWN/null、complete/exclusive false、release 0 保持。

## 旧固定源码与真实原件复核

第一旧 D `605a2a38d1db5ef85c961b4d357cafa157bdd7d5` 的 bootstrap：HELLO 后必须读完并验证
BIND/package 才进入 dispatcher；原传输记录 BIND/package 未写。
第二旧 D `59d7c32bbe10d580603b8e5e62dd49ad6a538e56` 的 dispatcher，SHA-256
`30d8e9fe9a9bbf39dc5261d0eb0d47c7349fe7e8229132f394a31aa934216eb4`：
`dispatch` 必须先完成 `admit`，其 `_admit_collect_policies → _admit_sudo_output` 位于
旧 scope observer、capacity、install、case intent/业务 unit 之前；该错误没有继续执行分支。
freezer 固定核验两历史 D/tree/source 摘要及祖先关系，不用修改后的当前代码解释历史。
没有恢复未保存的 sudo 原始 stdout，也不据此猜测旧原文具体格式。

同一既有管理 anchor 的十原件以 O_NOATIME/no-follow/原 owner/mode/单 link/稳定 fd/name 读取，
同时核验两个 remote-result 缺失。host/guest 独立消费者 PASS，合计 18390 B。
第一批五件 9318 B 原 pins 不变；第二批五件 9072 B，实际长度依次为 marker 3577、stdout 2852、
stderr 23、capture-manifest 1503、receipt 1117；摘要与 A 全匹配。
这是有限 pre-business 前提与原件绑定，不证明历史监督退出、usage 或业务成功；两旧仍 UNKNOWN、不退款。
未发任何 SSH probe，未创建新 marker，未修改旧现场。

## 本地定向验证与历史待办

标准进程 umask 022，核心定向 `1273 passed / 35 skipped / 19.57s`。
新增双旧结构/交叉篡改、十原件、混合合法静止分支、观察顺序/槽失败、最终身份漂移、
三批容量、固定新身份、历史代码 pins 和新批准链回归。合成链不当成实机验收。
开发过程中的未同步 fixture、测试变量/导入错误均保留为开发失败，不计 PASS；
一次沙箱回归为 `1217 passed / 35 skipped / 1 failed`，失败源于既有测试在用户目录创建
临时目录遭只读沙箱拒绝；使用正常用户测试权限后上述核心定向通过，未放松源码权限检查。

后续必须冻结实际 D，完成准确完整 source、独立 installed、CI 和真实私料双构包。
再单独登记仅已审 dispatcher digest，并对最终发行 D 重验全部 S2 条件。
S3 正式 caller 必须取得新的原 900 秒窗口，重新核验来源、身份、双构包、192 MiB/48
及六名 absence，全部通过才能执行获准的唯一 05b 请求。
H01 PASS 后才 Q4，Q4 PASS 后才 H11；任何失败保留现场结束本次范围。
在该早期检查点，真实任务未执行、新结果和证据未收回；生产 E3 与全部暂停支线保持。

## 准确实现 D 的 S2 与单独发行登记

实现 D `c6afff10656624cccbf554688e730f6bde6d82b7`，tree
`acd184ea5b0374591a505e7f950d8d8cebde224b`，直接以独立 C 为父。
独立 clone 完整源码 `5183 passed / 127 skipped / 456.46s`；JUnit
`lhqcore-post-sudo-verify.Q5qOW3ii/source-tests.xml` SHA-256
`a4964281dd616fb51128778bcc52703ba477b3c876bc27c6a00355337fa2804d`。
skip 包括需 root 的 fixture、未配置 MCP extra 和真实环境限制，均不当 PASS。

同 clone 新 venv 独立 installed verifier：PASS，94 checks / 292 commands。
`installed-acceptance/report.json` SHA-256
`a2147f4fd5a4ef47ed76111ef42a68fdc90f65362e5b4d26e9e0e13dacf0ba94`；测试 wheel SHA-256
`863527788a14b2dad004efda817a6ea66558e9d614fbd6b3aa187b9129639a26`。
测试 wheel 不替换现场原 wheel。[准确实现 D CI](https://github.com/kongbu0621/infra-local-hand/actions/runs/37277874571)
三个 job 均 success，已核对 Linux、Windows、classify-change。

真实私料 source-aware 复核与同 caller 两次独立构包/解析一致：860 members，18173580 B，
package SHA-256 `ca9fa728577329edad728da7f0c77d28c45e2e2599f0b4d99d0b343e02269313`；
manifest SHA-256 `2f688511ef80bb3a9e587aecab77ad5f3b99601fb3978c94e4754937fced4bca`。
approved-input 338750 B，SHA-256 `985c32eaf3418d39e0ac491cd01e2f5b767e62c4ca3136412e6a1cc5d9791077`。
十旧原件和 source/horizon/locator/policy 来源均通过；未采样现场前容量、未建 marker、未发请求。
该只读 caller 已结束，包/writer/window 不能复用为正式验收。

在以上全部通过后，仅登记 dispatcher SHA-256
`319c651f05998f812ac8faab51a354c7445b584bc6442a26c9800e79ae776e96`。
此独立发行登记不改 loader/bootstrap/dispatcher；field 尺寸分别 2160/49031/447075 B，均在原 cap 内。
未知摘要、未完成 readiness、来源/身份/窗口不一致继续拒绝。
最终发行 D 必须再次完成 source、installed、准确 CI 和实际私料双构包；未完成前不得执行 S3。

## 最终发行 D 的完整 S2

最终发行 D `8704a24b6c3c79ce4a36028ae2182dec2a35843e`，tree
`89a5f221883c11838a10a452be2dcb756abb5a17`，直接承接上述实现 D；只有摘要登记及其测试/记录，
未改变 loader/bootstrap/dispatcher。以下全部验证结束后才发出请求，正式窗口内没有替换 D。

- 独立 clone 完整 source：`5184 passed / 126 skipped / 456.46s`；JUnit SHA-256
  `7b2405613dc7bc18ba4b1205d35ec75fb2631d7e76fde01a82481fd3669d6731`。
  与前一轮一项 PASS/SKIP 差异来自既有普通 proc 资格测试的现场观察，并非修改测试或把 SKIP 转为成功。
- 新 venv 独立 installed：PASS，94 checks / 292 commands；report SHA-256
  `7b16e30834f181a917bd9ec403c9d7c2265a5f7c2c86918d0268091efd38a332`。
  测试 wheel SHA-256 `bf5976e8c555f63080f93f0c38fde1c073e0d503202a5716cba53e4ecaf0e215`，
  不替换现场原 wheel。
- [准确 D CI 37279434388](https://github.com/kongbu0621/infra-local-hand/actions/runs/37279434388)
  已于请求前核对 completed/success，classify-change、Windows、Linux 三 job 全部 success。
- 实际私料离线双构包：860 members、18173580 B，package SHA-256
  `f997231c1617909df6ba5bf73a8a5a1033210ac98e22119a452fdb1cc78bb084`；manifest SHA-256
  `3cf449e7e091687a542ca1883dc37b1aa62e1ccee0e2f31ee09404cddb1a11da`。
  approved-input 338750 B，SHA-256
  `5d227ecbef0eb0b72a3c5ddee998c1505b88ddf70d3c3c506e262144c25198da`。
  此只读窗口结束后没有复用其 writer/window。

完整原始本地验证报告保留在私有临时验证目录 `lhqcore-post-sudo-release.W6gVPJ1V`。
现场 candidate `4b6e4a7c403362358192086b88679e1326dcb2e1`、原 wheel SHA-256
`ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`（288375 B）与 projection SHA-256
`55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d`（11811 B）均保持原批准值。

## S3：唯一 05b 的真实失败与留存

2026-10-05 +08:00，最终全部 S2 通过后，同一正式 caller 开启新的原 900 秒双时钟窗口，
重验 held 管理 anchor、writer、十原件、source-aware 真实材料、两次独立构包/解析、
192 MiB / 48 inode 可用量及六名 absence，然后只创建一次 marker、只发一次固定请求。
正式包 860 members、18173610 B，SHA-256
`dc30af5fed782615501df61c601461ca3d214d379e8805d86e4f0dc458b6a498`；manifest SHA-256
`bb7c854f7279a352064de3f9bb260f92d7a0c8456a636cda747b363ac9481d2a`。
正式包与离线包的 writer/window 不同，不能混用摘要；approved-input 摘要保持上述值。

真实传输事实：execve 成功、HELLO 有效、BIND 与完整包写入，stdin 18174538 B 并 EOF；
wait status 3、stdout/stderr 均 EOF、host deadline met。stderr 为 24 B 的
`CORE_ADMIT_SSHD_GRAMMAR` 加换行。原 live finalizer 返回 `STOP_AND_RETAIN`，缺
`CORE_OUTPUT_MISSING`；没有 remote-result 或任何 case verdict。caller 自身正常返回不代表验收成功。

以下五件原始文件保留在同一私有管理 anchor，事后仅做本地 O_NOATIME/no-follow/稳定 fd/name
读回；无任何后续远程连接。总逻辑 9073 B，5 inode，最大观测分配 20480 B；不声称完整文件系统峰值。

| 05b 固定 capture 后缀 | bytes | SHA-256 |
| --- | ---: | --- |
| carrier-consumed.json | 3577 | `3d38e232e66580d588f03cfd444e5d1729904af801dfeb83af51f87e721d6c20` |
| stdout | 2852 | `cde70ed0b21d2b6cc7c5d9a21652c68f7e0f3b171e7ee03627eb594b56204f3f` |
| stderr | 24 | `7c8bda65cecc5daeba8693865946e37aed794bdb930f1f71e0fe0ddb9c8684de` |
| capture-manifest.json | 1503 | `fd9e85a9b368cfaf58c3138b9860f3d4ba3c4370fa2319e8c992f04d64f23918` |
| acceptance-receipt.json | 1117 | `1274a7522d4f7151f894fbf530618cba12ba8134b1dd162731cb32c72f43929b` |

没有输出包，因此原 receipt 的 `real_task_execution` 和 `result_evidence_collection` 均保持
`UNKNOWN` / null。失败传输证据确已收回，不等于正常业务结果和验收证据收回。
准确已发 D 的静态顺序将错误定位在 `_admit_collect_policies → _admit_sshd_source`：
sudo 来源及输出校验之后、sshd helper/有效配置查询之前，也在两旧 scope 核对、guest 容量、
安装和 H01 intent/业务执行之前。错误不是 sshd 有效输出解析错误。
这支持“本次停在业务前置准入”的有限判断，不证明远程监督闭合或 guest 使用量，也不提升原 UNKNOWN。
原 24 B 错误没有失败行或 sshd 原文；不能凭常见默认配置猜测实际触发行，不能新增连接补采。

本次当前 host 容量条件通过；三条完整 capture 承诺共 192 MiB / 48 inode，release 为 0。
complete-host-admission/exclusive-reservation 仍 false，更早 host obligations 仍 UNKNOWN/null。
两旧历史及全部承诺保持；因尚未完成 guest 准入，不声称其当前静止、容量或使用量已经验证。

## 范围终点与直接阻塞

05b 与此前 03a/05a 均已消费。本次没有取消/恢复执行，没有清理、退款、重连或第二请求。
失败留存后仅关闭发行 allowlist 并验证该安全收口；不修改已发 field bytes 或把失败变成下一批。
本地定向 entry/freezer/post-sudo 回归 `145 passed / 5.67s`，`git diff --check` 通过。
此收口验证与已发 D 的完整 S2 分开记录，不把前一版本的全量结果转给后续提交。
本 scope 已按失败停止规则结束，不等于核心验收通过或 Gate 被重新用作第四次授权。

直接阻塞是 sshd 源配置语法准入拒绝，且现有失败输出不足以确定触发行。后续需在适用的开发授权内，
以可核验来源定位该解析/输入不一致并完成回归，冻结新实际发行版本；任何新增现场请求都需其独立准确
批准链，不能复用本次窗口。只有正常链实际通过后才能继续 Q4 取消和 H11 同账本/同 unit 恢复。
production `E3_SUPERVISION_UNVERIFIED`、namespace/watchdog 及所有其他暂停/未授权范围保持。
