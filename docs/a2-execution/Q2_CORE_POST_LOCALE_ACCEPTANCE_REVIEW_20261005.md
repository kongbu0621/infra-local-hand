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
