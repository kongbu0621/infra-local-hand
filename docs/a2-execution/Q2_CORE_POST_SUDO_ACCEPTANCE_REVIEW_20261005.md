# sudo 修复后单次核心验收实现与验证

2026-10-05 +08:00。范围 `LH-Q2-CORE-POST-SUDO-ACCEPTANCE-v1`，仅 S1–S3。
当前检查点：S1 已交付，实现 D 的 S2 已通过；最终发行 D 仍须完成自身重验；S3 未发请求。
05b marker/request 均 NOT_ISSUED。独立摘要登记只接受已审 field bytes，不替代最终 S2 或当前准入。
不得复用旧批、重试、重连或清理。早期“空 allowlist”是前一检查点，以下登记在实现 D 验证之后。

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

## 本地定向验证与待办

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
当前真实任务未执行、新结果和证据未收回；生产 E3 与全部暂停支线保持。

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
