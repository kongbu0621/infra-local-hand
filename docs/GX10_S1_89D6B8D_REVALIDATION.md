# GX10 S1 隔离实机复验记录

日期：2026-09-22。

## 结论

固定产品候选 `89d6b8d807287396d4bac102d5fa8057558c3c7e` 已在 GX10
Linux/aarch64 实机上完成隔离复验。正常 fixture 中没有复现 outbox 残留，但复核发现
安装态验证器使用 `Path.exists()` 证明部分目录项已经删除，可能把 dangling symlink
误判为不存在。该 false-PASS 缺陷通过确定性反例和测试优先红轮确认。

修复候选为 `d3a629d1de7a494ac4c19bc95f88be9eab332733`，tree
`64e3727355710c2c3b987101250adcac6cf2c0f3`，唯一父提交为原候选。修复仅涉及
`tools/verify_installed.py` 和九个测试文件，没有修改 Worker、controller、协议、八项
动作、依赖或部署配置。修复后在另一套全新 checkout、build/runtime venv、wheel、
acceptance 和 evidence 目录中完成正式复验，结论为 **PASS**。

## 验证结果

| 轮次 | 源码测试 | 安装态 | 结论 |
| --- | ---: | ---: | --- |
| 原候选 `89d6b8d...` | 297 passed / 0 skipped | 93 checks / 291 commands | 正常 fixture 通过；验收器存在已确认的 false-PASS 缺陷 |
| 修复候选 `d3a629d...` | 299 passed / 0 skipped | 94 checks / 292 commands | PASS |

- 两轮合计保留 784 条命令和 1,568 份 stdout/stderr 日志；封存时逐项重算摘要。
- 修复候选 wheel SHA-256：
  `5ce39b5ac80e76fecb4197b709488cdbac8736e34282d194e9e1a163a66dff49`。
- wheel 的 23 个产品 payload 逐字节绑定修复候选 Git blob；包核心 digest 保持
  `3f3d141395d3d56e0cf599491c09e4c491a5f83c998d0b56ed38898a0105968f`。
- LH9995 与 LH9804 的恢复时序证据证明 pending 真正删除，重复 submit/worker
  不重放 CAS；LH1020 至 LH1022 的异常 Unicode Result 隔离、屏障和后续健康任务均通过。
- 现役服务只读观察的前后状态一致；没有停止、重启、切换或提交现役任务。

## Public 主干对应关系

修复候选 `d3a629d...` 保留在 GX10 原始 Git bundle 中。公开主干提交
`b12e9c06cdee0094bd79661eb28201fb10a26db3` 以交接提交
`91cb5954b84528d2d08970ca507ef98e64380aa9` 为父提交，包含相同修复：

- 两者变更的十个验收器／测试路径完全相同，文件字节全部相同；
- Worker、controller 及其余产品 payload 全部相同；
- 两个 tree 的其余差异只有四个公开复核／交接文档。

因此 GX10 实机结果支持当前 Public 主干的可执行代码和验收器内容；不把
`b12e9c0...` 记作实机上直接执行的提交。

## 证据封存

完整证据 ZIP 未提交 Public 仓库。其外部封存信息为：

- ZIP SHA-256：
  `f237102e2572f8449b81c53516349bb68c591af12fb609db373e0e2b917f828a`；
- ZIP 大小：13,518,858 bytes；成员数：9,251；
- manifest SHA-256：
  `3673ad8566ae24c720242d43d9466f2743cff1c3965711457dbfc664a846f810`；
- 中文报告 SHA-256：
  `2824b9d2ebe1e38777843975e7bb7a14b5433813a08f23245299f0da3f91bc94`。

独立复核重新计算了 ZIP、seal、manifest、9,250 个受封存条目、两轮命令日志、
JUnit、wheel RECORD、产品 payload 与 Git blob，对应关系全部闭合。原始机器证据、
本机路径、服务配置和 Private companion 内容继续只在私有证据包中保留。

## 保留边界

- 先前云端两次 outbox 残留在 GX10 正常 fixture 中没有复现，其环境时序根因仍未查明；
  本轮不把验证器缺陷写成该历史现象的根因。
- `/proc/<pid>/exe` 因现有权限不可读，按 `UNAVAILABLE` 保留，没有提权或改写为 PASS。
- Windows、现役服务切换、S2 和 artifact-ledger A2 尚未执行。
- S2 必须先形成单独的配置、迁移、互斥写入、切换、验收和回滚方案，再取得授权执行。
