# locale 修复后单次核心验收：实现与验证

范围 `LH-Q2-CORE-POST-LOCALE-ACCEPTANCE-v1`，仅 L1–L3。
此检查点交付 L1；L2 准确版本验证尚未完成，发行 allowlist 为空。
05c marker/request 均未创建，H01/Q4/H11 未执行，没有新的业务结果或证据。

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
