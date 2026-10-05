# locale 修复后单次核心验收：实现与验证

范围 `LH-Q2-CORE-POST-LOCALE-ACCEPTANCE-v1`，仅 L1–L3。
最终状态：L1 和最终发行 D 的全部 L2 已完成，L3 的唯一 05c 请求已发出。
guest 返回 `CORE_CAP_INSUFFICIENT`，本批失败并保留，发行 allowlist 再次关闭。
05c marker/request 均已消费；尚未进入 H01/Q4/H11，没有业务结果包。
原 receipt 的业务执行、业务结果回收均为 UNKNOWN，不把传输失败证据当成业务验收通过。
下文未发出、待验证等文字是历史检查点，由最后的 L3 结果取代。

## 授权与实现边界

R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 已从直接固定来源完整读取。
A `a243362d473891469b012a0ab8c3bd221794aa50` 三文档及摘要保持不变。
[Owner 逐字决定](../governance/Q2_CORE_POST_LOCALE_ACCEPTANCE_OWNER_DECISION.md)及根 Gate
组成独立 bookkeeping-only C `fe635c4885b8f31dd13901bef47e619480b2eda3`，
tree `e72aa24f0ec039730bcb75f2ccafc1eb0145b948`。实现单独承接 C，不 squash。

新身份固定为 `lhqcore-20261005c`，三 case UUID、21 个 project、安装与 capture 名称按 A。
业务 candidate、wheel、projection、各批预算和 900/800/750 秒时限不变。
loader 不变；bootstrap 只有等长批次身份替换。freezer 强制核验 locale 修复 D 的
`_admit_sshd_source`、`_admit_text`、`_require` 源字节保持，不重放已保存配置的解析。
生产 `E3_SUPERVISION_UNVERIFIED`、暂停支线及一次失败即停止的限制保持。

## L1 交付

- 三个固定 prior/v2 profile 分别核验原 D、包、HELLO、传输及失败 receipt；
  reconciliation/v4 和 historical-obligations/v4 仅接入获批增量。
- 四份诊断原件只在本地以稳定 fd/name、O_NOATIME、无 symlink、0600 单 link
  与 owner/device 校验读取；与十五核心原件共享 inode 去重。
  原 marker/receipt/stream hash 关联通过才生成 metadata-only 保留对象，原文不入包。
  reader 完成不提升为独立监督完成，管理退出/usage UNKNOWN 和 4 MiB/8 承诺保持。
- 三个旧 scope observer 同时保留句柄；按 03a A、05a A、05b A、原容量与 manager、
  03a B、05a B、05b B、全部最终复核的顺序执行。
  六个 SHOW 槽各一次，失败不得前进或重入；helper 使用量仍归原 carrier。
- guest 三旧完整承诺逐设备叠加，加新一次及更早义务，不退款。
  四核心 carrier 的前置 4 GiB/512 配置上界不包含诊断、管理祖先及无关负载。
- host 五行容量条件/v3 精确为 260 MiB/72，绑定诊断摘要、三旧摘要、实际 D、
  原 writer/anchor/window，返回端独立重验；不是排他预留或完整历史容量证明。

## 开发回归与待验证项

核心定向回归在正常用户权限、umask 022 下：1583 passed / 35 skipped / 23.60s。
skip 保持为环境限制，不计入实机 PASS。随后补充了 decorator 字节保持和诊断容量篡改回归，
须在冻结版本验证中一并执行。

开发阶段曾因未同步旧测试的两批断言、fixture 参数和错误类型产生失败，修正测试后验证。
一次沙箱核心运行为 1559 passed / 35 skipped / 24 failed；失败涉及非标准 umask 的
文件保护前置拒绝及既有用户目录临时 fixture 被沙箱设为只读。没有放宽实现校验。
上述开发运行不能代替准确 D 的完整 source、独立 installed、CI 和真实私料双构包。

必须先完成全部 L2，再单独登记已审 dispatcher 摘要，并对最终发行 D 重验全部门。
正式 caller 使用新的原窗口，重验十九原件、双构包、容量及六名 absence 后才可消费一次 05c。
此前三旧核心 UNKNOWN、诊断未独立监督及全额承诺保持；没有新执行或清理授权。

## 准确实现 D 的 L2 检查点

实现 D `29e2c6cfb3897a07edae8c0464d5b794fed3473c`，tree
`c3234727bb6fd508b401278c900f9c786d17eaa4`，直接以独立 C 为父。
三 field blob 尺寸为 2160 / 49031 / 452409 B，均在原 cap 内；
dispatcher SHA-256 `714bbb8039aadc3ab58195adde1f61cc273cb4822b46e60de26c2315d459a11b`。

- 准确 D 核心定向：1587 passed / 35 skipped / 25.90s；JUnit SHA-256
  `f85b6f360c70efb72621f991034d5585c2ee51de0a78fc8272221fc2d67f0796`。
- 独立 clone 完整 source：5582 passed / 126 skipped / 464.90s；JUnit SHA-256
  `f9df4ef5e1eaa77d6a449f4ee07e62a619d2b8dc86d5e19327331b9cf8214e08`。
  skip 包含 root fixture、可选 MCP extra 和真实环境限制，不当成实机通过。
- 新 venv 独立 installed：PASS，94 checks / 292 commands；report SHA-256
  `2f4359ebc1a73db5c0297006a653122fb64a0c12b18a1c76736f8d63c9f5418d`。
  测试 wheel SHA-256 `e53263454e72b2d8ebd0018dde04c97f108594325da30b4011f9603c41eaf978`，
  不替换现场冻结 wheel。首次构建与源码测试共享 clone 时，被 provenance 的缓存稳定性检查拒绝；
  失败保留，改用另一个相同 D 的干净 clone 构建，不放宽检查。
- 实际私料 source-aware 复核、两个独立内存构包及解析通过：860 members，18193634 B，
  package SHA-256 `bd202cac3ff80479cdec14653b874f888fbcffbddf2a12041a6713c0936c5e71`，
  manifest SHA-256 `929d03df69e77512df36a3435911b9492f12ad0d5d89de4dd1cba4a3806363d3`。
  approved-input 353470 B，SHA-256 `0eb21437111ec421e55a857e52931d67a596763c91f408a8662670823c141e95`。
  十五核心原件 27463 B、四诊断原件 8782 B 均通过固定 hash 与关联检查；没有配置原文入包。
  没有执行旧 capture、重放私有配置解析、采样新 host 容量、创建 marker 或发出请求。
  只读 caller 已结束，writer/window 和包不可复用为正式现场窗口。

本地原始测试报告保留于私有临时验证目录 `lhqcore-post-locale-verify.KFoctjWH`。
此处记录的本地结果尚须结合准确 D 的完整 CI；不得据此单独开始现场执行。

准确实现 D 的 [CI 37325603575](https://github.com/kongbu0621/infra-local-hand/actions/runs/37325603575)
现已 completed：classify-change、Linux、Windows 三 job 均 success。
以上全部通过后，单独登记且只登记 dispatcher digest
`714bbb8039aadc3ab58195adde1f61cc273cb4822b46e60de26c2315d459a11b`；
该发行登记不修改 loader/bootstrap/dispatcher，不纳入任何已消费批次摘要。
最终发行 D 的完整 source、installed、CI、真实私料双构包仍须再次通过，尚未开始 L3。

## 最终发行 D 的全部 L2

最终发行 D `657b1bcd749cb4281b0193b2bc9430b0662faf98`，tree
`4bb00b2e9ccbec3c43160159811e51eec76702cd`。它只登记发行摘要和验证记录/测试，
与实现 D 的 loader/bootstrap/dispatcher 逐字一致。

- 独立 clone 完整 source：5582 passed / 126 skipped / 460.05s，JUnit SHA-256
  `863407af4b44a17e97cf3c2056d3515fe09195293fb6225deb1cd970439981ec`。
- 新 venv 独立 installed：PASS，94 checks / 292 commands，report SHA-256
  `5413a9879f350ec9cc54b506562bf65a020142dbf507c27db39d8e22c05abdd6`。
  测试 wheel SHA-256 `31d2872409868e88f74231ffcc36ef7cba937bd4dc1d33dafd3131e62e4871ec`；
  原现场 wheel 未替换。
- [准确 D CI 37327721574](https://github.com/kongbu0621/infra-local-hand/actions/runs/37327721574)
  completed/success，classify-change、Linux、Windows 三 job 均 success；在现场请求前已核对。
- 真实私料离线双构包/独立解析：860 members，18193634 B，package SHA-256
  `044c83c6649cc1c9f6faa9754cfe7af35744a89ed562c9190c4a8715e8363a2c`，manifest SHA-256
  `801080b5df06fbda403ef00489e7ab38d453fc1c7cc2a19760d45250755936ad`。
  approved-input 353470 B，SHA-256 `169c6e8cef5a3d6ee94d7cf433996016710b5e5613a7158e57875baad09ee793`。
  十九原件与 source-aware 来源均通过，诊断原文不入包；没有消费请求。

原始验证报告保留在私有目录 `lhqcore-post-locale-release.cxG0yk4s`。
源/安装/CI PASS 不是实机 H01/Q4/H11 PASS。

## L3：唯一 05c 的真实结果

2026-10-05 +08:00，全部 L2 门通过后，正式 caller 在自己的原 900s 双钟窗口中重验
十九原件、held 管理 anchor/writer、两次独立构包、260 MiB/72 容量条件和六名 absence，
仅创建一次 O_EXCL marker、仅发出一次固定 carrier。没有复用离线 caller 的 writer/window。

正式包 18193664 B，SHA-256 `0acdfcaad942191b85f9bf24832c08d2c344fee3fe392a41d376a84ec2271184`；
manifest SHA-256 `28cc514a5c622720744dc7633520c2ee326b7a5681276bfbaebb975f882264db`。
approved-input 摘要与最终发行离线验证相同；包的 writer/window 绑定不同，因此包摘要不同。

真实传输：execve 成功、HELLO 有效、BIND 和完整 package 写入，stdin 18194592 B 并 EOF；
wait status 3、stdout/stderr 均 EOF、host deadline met。stderr 为 22 B 的
`CORE_CAP_INSUFFICIENT` 加换行。原 live finalizer 返回 `STOP_AND_RETAIN` / `CORE_OUTPUT_MISSING`。
caller 进程返回 0 仅表示失败收口完成，不是业务成功。

五件已取得 capture 保留在原管理 anchor；按原固定 source locator 做本地 no-atime 读回复核，
摘要与 live finalizer 一致，没有新增远端连接或补采。首次仅凭目录形状推测的本地 stat 未找到文件；
未据此判定证据丢失，随后使用固定已保存 locator 确认了原位置。没有搬移或更改原件。

| capture 后缀 | bytes | SHA-256 |
| --- | ---: | --- |
| carrier-consumed.json | 3577 | `ac0314d584ce7dfdbe5892f779cfbc01a702459fb31ab539b2752f70c07f7deb` |
| stdout | 2852 | `ff0f1b11037028b766c6bf8d4b6623f84241541f9e9240bf1f90efe3c9d6f7e9` |
| stderr | 22 | `e1c59576e732df777e6542b880a21994430f06f72ca54d9a0319507d1126aa75` |
| capture-manifest.json | 1503 | `44398704da222ff3d5200b53dfbc732c1ad23fa4b35bd4d75e4671c5b8d5b406` |
| acceptance-receipt.json | 1117 | `184439515c226a8b108b270522800174a7adb476191a606a66b7d451c25e601c` |

合计 9071 B / 5 inode，最大观测分配 20480 B；不声称完整文件系统峰值。
没有 remote-result，H01/Q4/H11 均无 verdict。
receipt 中 `real_task_execution` 和 `result_evidence_collection` 均为 UNKNOWN/null。

准确已发 D 中，此错误仅位于 `_cap_charge` 的逐设备剩余容量判定：任一 pool 的可用 bytes/inodes
不足“全部历史承诺 + 新完整承诺”即拒绝。静态调用顺序为策略/身份检查、三旧 A 观察、
容量准入，然后才 manager、三旧 B、安装及 case。结合该错误，只能得出本次到达 guest 容量
准入并在安装/业务前停止；不能据此声明三旧完整 A/B 静止、远端监督闭合或用量已验证。

本次 host 的 260 MiB/72 条件通过，不等于 guest 容量通过，也不是排他预留。
更早 host 义务、三旧核心历史及诊断未证明边界均保持 UNKNOWN；所有承诺不退款。

## 范围终点和直接阻塞

05c 一次机会已消费。本范围以失败留存结束，未重试、重连、补采、清理、改配置或重启业务。
发行 allowlist 已关闭；原生产 E3 和暂停支线保持。

关闭后的 entry/freezer/post-locale/host-capacity 定向回归为 248 passed / 7.68s；
`git diff --check` 通过，loader/bootstrap/dispatcher 与已发 D 逐字一致。
此验证仅覆盖本地消费后封闭，不是新的现场执行或 H01/Q4/H11 通过。

直接阻塞是 guest 的逐设备容量准入。原返回只有拒绝码，没有失败设备、实时可用量或差额；
不能猜测是哪块盘、将 host 空间代入 guest、清零旧承诺、放宽阈值或当场增额。
后续须先明确保留全部承诺下的容量处理依据；若需要新现场读取、变更或另一批执行，
须单独固定其准确范围和批准，不能复用 05c。本轮不自动创建下一批。
