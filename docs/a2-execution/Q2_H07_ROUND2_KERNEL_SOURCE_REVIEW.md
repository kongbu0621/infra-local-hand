# H07 第二轮：准确 Azure 源码包复核

2026-09-30。只读研究，补充[第二轮原件复核](Q2_H07_ROUND2_RESULT_REVIEW.md)。
**准确官方 Ubuntu 源码包已确认缺少上游修复；原运行内核二进制与实际 SIGKILL 发信来源仍未取得动态证明。** 本结论不改变原失败或第三轮停止。

## 准确来源及完整性

原报告记录 kernel release `6.17.0-1022-azure`、image `20260920.314.1`；
[GitHub 对应 image 说明](https://github.com/actions/runner-images/blob/ubuntu24/20260920.314/images/ubuntu/Ubuntu2404-Readme.md)列出同一组合。

从 Canonical 官方 HTTPS archive 取得源码包 `linux-azure-6.17` / `6.17.0-1022.22` 的
[签名描述文件](https://security.ubuntu.com/ubuntu/pool/main/l/linux-azure-6.17/linux-azure-6.17_6.17.0-1022.22.dsc)、
[完整原始 tar](https://security.ubuntu.com/ubuntu/pool/main/l/linux-azure-6.17/linux-azure-6.17_6.17.0.orig.tar.gz)及
[完整版本 diff](https://security.ubuntu.com/ubuntu/pool/main/l/linux-azure-6.17/linux-azure-6.17_6.17.0-1022.22.diff.gz)。
两个包的字节数和 SHA-256 均与 `.dsc` 相符；未另行验证其 PGP 签名，不将 HTTPS+摘要等同独立签名验证。

| 对象 | bytes | SHA-256 |
| --- | ---: | --- |
| `.dsc` | 5339 | `52c559ca2f980cad03b4107da9d95d76f6f94da3597fa4e16afd5bdd1c0f01f4` |
| `orig.tar.gz` | 248671329 | `a5623ec5af79da8807e1467e43a1888461c7a445fb1e17533fe45f0fdf4394e3` |
| `diff.gz` | 3218463 | `cb0154101fc7e337228a00c1caae7760b88afcb033f75c01756b3669dd376c54` |
| 重建后 `kernel/cgroup/cgroup.c` | 195921 | `fe7ce87fe8d71125ba4f6d8dc3e6764c1285ef13c774a7f9cd7ead178728a389` |

从 tar 抽取该文件，并应用版本 diff 中其全部两段修改；patch 成功，无模糊匹配/拒绝。
两段只改变 `cgroup_get_from_id`；完整13,146,842字节解压 diff 不包含 `kill_seq` 或 `CLONE_INTO_CGROUP` 修改。
[机器可读来源索引](evidence/q2-h07-cgroup-fence-spike/round-2-kernel-source.json)保留全部来源URL、原文件摘要、行位及证据边界。独立研究者与主审分别核对摘要和关键代码。

## 源码层结论

Linux 官方修复 [8e359920216689b3b79e0fe8961a77fe312a511f](https://github.com/torvalds/linux/commit/8e359920216689b3b79e0fe8961a77fe312a511f)
在解析出目标 cgroup 后重新取得目标的 `kill_seq`，避免把父组序号与目标组序号错误比较。
重建后的上述 Ubuntu 准确源码仍是未修复路径：

| 准确文件行位 | 源码事实 |
| --- | --- |
| 4089、4114–4115 | kill 对目标及每个存活后代递增序号，空组也递增 |
| 6597–6600 | 目标尚未解析，先快照父组序号 |
| 6662–6664 | 写入目标 cgroup 后返回，没有重取目标序号 |
| 6795–6801、6836 | 从目标取得新序号，再与先前快照比较 |
| 6859–6861 | 不相等则向新子进程发 SIGKILL |

fixture 的 probe 杀 B 子树，增加 B/S/W 序号；G 不属于 B，随后从 G 向复用的 B/S
创建 S，正好具备上述不同序号的条件。第二轮原事件记录 S 创建后约2.075ms退出，早于已记录的关闭动作。
这是有准确源码支持的强机制解释；它不等于运行时信号来源追踪。

## 剩余证据边界与设计影响

原报告没有 Ubuntu 完整 build/package identity、内核二进制摘要或 livepatch 状态；release/image 相符仍不能独自把源码包与当时执行字节完全绑定。因此“准确源码包缺修复”已经查明，“当次实际发信来源已动态证明”仍不成立。原复核中当时未知的源码包问题由本补充消除，原报告与当时记录不倒改。

拟议修复采用共同 E 下每个 probe/病例的独立 G/B/S/W 对象；仅在 probe 后重建一次不能覆盖后续各 case 杀树后的再次复用。新路径不依赖在 runner 上安装/升级内核，也不声称兼容所有缺陷内核：新 runner 的 probe/权限/六案仍须逐项取得事实，不满足仍停止。

本轮未运行 reproducer、真实账户/cgroup/probe，未改变主机配置。源码研究不消费实验轮次，也不解除第二轮 UNKNOWN 的跨轮阻断。新的[三层方案](q2-h07-r2-continuation/REQUIREMENTS.md)及其 Owner 决定独立处理受影响范围。
