# 核心 host 容量边界实现与单次验收

2026-10-05 +08:00。本记录对应已批准的 `LH-Q2-CORE-HOST-CAPACITY-BOUNDARY-v1` B1–B3。
容量条件只证明采样时普通 writer 可用量满足两项 core 承诺；更早 host 承诺仍 UNKNOWN，
完整 host 历史准入与排他空间预留均为 false。生产 E3 限制和暂停支线不变。

## 准确授权与实现

R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 已直接读取，完整性沿用根声明。
A `f491b15514ed0e05f7e1924785a3f7d162dae90f` 的三个文档原字节保持。
[Owner 原文](../governance/Q2_CORE_HOST_CAPACITY_BOUNDARY_OWNER_DECISION.md)与 Gate 登记构成独立 C
`434c6a07f7a84f26d7bd01de138125debc467dd4`；其中没有代码或测试。
实现 D `61e232e1a4b57c9b7fbd523cbd7d4f8f747d756e`（tree
`a7982bf0f410d91c5e3368340a0d3a54b215aff8`）直接以 C 为父提交。

D 在原 pre-marker 点核对旧五原件后，仅调用一次受原 deadline 包裹的 `fstatvfs`。
调用前后检查完整 held fd/name 目录身份、权限、UID/GID/nlink 及实际 writer；双钟顺序不变。
当前可用量要求固定 `134217728 B / 32 inodes`；不扣除旧五文件的小额实际分配，不退款。
条件记录绑定实际 D、management digest、prior canonical digest、原窗口与本次观察。
记录沿原调用栈进入 finalizer 和 live 返回，再次严格校验；不重采样、不用成功说明覆盖后续失败。

包准备现在只读原件，不提前或重复采集容量。新 A/B/C 的 tree、祖先关系、三文档与 B 字节
加入原发行检查；不存在 caller 可选预算行。原 capture_accounting 五键、六个文件名、盘上格式、
wire、guest 计费和三个 field 文件保持；条件说明仅为 live 返回 sibling。

## 验证

核心定向回归 `1159 passed / 35 skipped`。新增覆盖阈值、坏容量值、身份/双钟漂移、
旧原件改变、pre-marker 零请求、返回记录篡改和 ENOSPC/EDQUOT/EIO 保留失败。
真实 package builder/parser 的合成接线测试不等于现场业务测试。

保留验证准备失败：默认 umask 0002 下，沙箱运行 `24 failed / 1135 passed / 35 skipped`，
普通环境运行 `23 failed / 1136 passed / 35 skipped`；主要是 fixture 文件组可写，另有沙箱 home 只读。
umask 077 下 `1 failed / 1158 passed / 35 skipped`，因为原 mkdir fixture 断言期望 0755。
使用标准 CI 的进程 umask 022 后上述定向回归通过；未修改系统配置、生产权限规则或旧断言。

准确 D 在独立 clone 构建测试 wheel、新 venv 安装验证通过：`94 checks / 292 commands`，fixture-only。
报告 `lhqcore-capacity-verify.zERhxt2g/installed-acceptance/report.json` SHA-256
`d09b0b4add98ee5940e38e72c2c743f3d72a504a513906486097bb9f05c232d0`；测试 wheel SHA-256
`7cdb7be20b3abae466ad468f2dd1d01badc202acfc86898cb61f16baf03f1e7a`。
测试 wheel 不替代原现场 wheel `ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`。

准确 D 的独立 clone 完整源码：`5070 passed / 126 skipped / 475.31s`，进程 umask 022。
JUnit `lhqcore-capacity-verify.zERhxt2g/source-tests.xml` SHA-256
`1c4cac853a30dd76ed8842008a77523bc6711ffd35c90f720cff6b5a5e1118ce`。
所有 skip 保留，不当成现场能力通过。
[准确 D CI](https://github.com/kongbu0621/infra-local-hand/actions/runs/37262540014)
已 3/3 success，Linux 源码及独立安装、Windows 和 classify-change 均已核对终态。
上述条件及下述真实私有双构包通过后，后续独立发行登记仅加入已审查 dispatcher SHA-256
`30d8e9fe9a9bbf39dc5261d0eb0d47c7349fe7e8229132f394a31aa934216eb4`，并保留未知摘要拒绝回归。
发行登记提交仍须自身准确 SHA 的 source/installed/CI 通过，才能在新的 live caller 中执行。
登记不消费 marker，也不放宽原 pre-marker 的来源、身份、当前容量和六名 absence 检查。

## 真实私有来源校包

复用已经定位的固定来源，未再要求搜索 44 份文件或重采 K4/R3。旧五原件全匹配，共 9318 B。
实际 cloud-init 与规范 grant、历史 guest 来源链及完整 source-aware approved-input 校验通过。
approved-input 为 325117 B，SHA-256 `ea650c23e2894d820aa591121fc93d141a0d37b2f3f76928234e9f90391bf7b1`。
实际新 held writer/anchor 的同窗两次独立 build/parse 相同：860 members、18149835 B，包 SHA-256
`9a90956b6ca728295a7ca6c1b87f6543f4d4f53e924a07315b742e43a908c7d6`；manifest SHA-256
`cbaf9efe7e7ac9c88963b17f2b772566a055e696d4cddb15ca1ce8d6a1d0b645`。

这是只读校包，不是可复用的现场包或窗口；未观察本次容量、未创建 marker、未发 carrier。
正式 B3 必须在新的原 900 秒 caller 中再次双构包及检查全部来源/身份/absence/容量条件。
原未消费机会、固定 session、预算、900/800/750 秒、失败不重试/重连/清理保持。
该记录目前不证明 H01/Q4/H11 执行，也不证明真实业务结果或证据回收。
