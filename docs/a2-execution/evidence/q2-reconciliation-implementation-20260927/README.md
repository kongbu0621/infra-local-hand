# 对账组件的验证与私有证据索引

准确 D：`8fd84521cdd25b455ff148e0c0fed6b5d8e39fe1`；tree
`5fb64e578d06e2954c1eedbc1b15e00069dc32a4`，父提交为独立 C
`1491765c64c60a63d6bddf10a049308e404885ca`。

- [定向验证](validation.json)：154 新测试 PASS、2 SKIP；115 旧相关测试 PASS，准确源码摘要及环境限制保留。
- [准确 D 与真实原件复验](exact-D-source-check.json)：42 Git 工具blob、48原件、冻结wheel及入口阻断核验。
- [实施结果和未完成范围](../../Q2_RECONCILIATION_IMPLEMENTATION_REVIEW.md)：非READY、无现场窗口/发行，不声称Q2接受。
- [新host顺序待审基线](../../../governance/Q2_HOST_WINDOW_CONSUMPTION_BASELINE.md)：准确 A `8402f0cc82d8a0ac0b9a56716bf276f41cafea37`，尚无新B/C。

机器原件、复原脚本、真实离线manifest、独立审阅与被否决初稿留在同一私有Git
证据归档 `q2-history-evidence-20260927.bundle`，不公开实际路径、账户或boot值。
最终私有commit `4265e540e41d4bfb1832f76c45ebfc2bfe222eee`，tree
`a064f774b386664234384c1e23db6cbe87efa429`，父提交为
`981d1ae0e774e3c0bc5a5de711003b714cf87709`，再前一提交严格保留
`14be72107572bc092c8b8aaf16abcdf5c99c7a87`。787项逻辑证据/468内容对象，
原750项和431原对象全部不变，本轮两次追加共37项。Bundle 52,357,782 bytes，SHA-256
`afc96a07275ee998881915ac52246a04587f57c547af53aa230d100b9da04124`。
fsck、bundle验证、全新clone及全部条目长度/摘要恢复通过。旧115测试结果保留为
本轮工具结果的明确转录，不伪装成第二次独立执行。新测试原stdout单独留存。

归档保留新A终审期间的原检查点，再追加最终IO独立复核与准确新A状态指针，
均明确尚无新批准；准确A与注册记录在公开Git历史中单独留存。原件已找到，不应要求Owner重复查找。新host顺序尚未
实现；缺现场树、Q1逐对象owner信息及其他实时前置仍必须在准确窗口内验证。
