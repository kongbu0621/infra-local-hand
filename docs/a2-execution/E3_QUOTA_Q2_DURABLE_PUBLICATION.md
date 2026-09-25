# Q2 第二批源码发布映射

日期：2026-09-25。仓库：`kongbu0621/infra-local-hand`，分支：`main`。
本地 Git 与 GitHub API 的提交元数据不同；用完整 Git tree SHA 证明发布源码一致，
不把另一份提交 ID 当作在本地重新跑过测试。

| 位置 | 本地提交 | GitHub 提交 | 相同 tree |
| --- | --- | --- | --- |
| 继承的第一批发布记录 | `63e7317b962920fc61a7dbf8374b63fccecda2a9` | `cecf17cf0bcfce123e3e5ac2a082feb5e57787f5` | `d304c2504ab25fdc36197259b94ad94c42ea9f51` |
| 第二批准确源码 | `4c550483a92eb5d13c9bd3d7ef42319fabebcace` | `05f5c68b3ace6b71ed6bc3baa14ccff1c57f209c` | `736ad69811bd293c97acbe7feb995c66922e1399` |

GitHub 第二批源码提交以上一远端提交为父；构造返回的 tree 与本地准确源码 tree 逐字匹配。
[107 项定向测试报告](E3_QUOTA_Q2_DURABLE_VERIFICATION.md)适用于表中第二批源码 tree。
本文件、验证日志及进度说明在随后文档提交中保存，其提交身份以 Git 历史为准，不额外构成一次源码测试。

发布使用已授权的提交推送流程：核对原远端 main、建立同树提交、非 force 更新引用，再读回分支身份。
本报告不记录尚未完成的新 CI 为通过，也不继承旧候选 CI 为本批结果。真实 IPC、guest/systemd/quota
和完整生产链验证的未完成状态保持不变。
