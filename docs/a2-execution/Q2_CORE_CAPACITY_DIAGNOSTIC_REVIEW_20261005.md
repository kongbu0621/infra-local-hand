# Core 容量拒绝的离线核算与诊断修复

2026-10-05 +08:00。本轮完成两项离线交付：复核 05c 的容量需求，补齐原拒绝路径的诊断。
没有证明现场容量问题已解决，没有新增批次、marker、SSH/carrier、补采或清理。
[05c 原始失败](Q2_CORE_POST_LOCALE_ACCEPTANCE_REVIEW_20261005.md)及四次核心请求的消费保持；
H01/Q4/H11 没有新结果，原业务执行和结果回收 UNKNOWN 不变。

这是既有 CLOSED 核心开发范围内的诊断修复：只改变失败说明，不改变准入谓词、历史来源、
预算、对象、权限、时限或发行状态。原 R 的直接固定来源已重新读取；没有新 Gate closure。
根指导和上次独立 C 所规定的未受影响开发权限不构成另一次现场执行权。

## 离线来源和核算边界

以实际已发 D `657b1bcd749cb4281b0193b2bc9430b0662faf98` 为对照。
当时 approved-input 的 SHA-256 为
`169c6e8cef5a3d6ee94d7cf433996016710b5e5613a7158e57875baad09ee793`。
本轮不重建整个私有包，不重新观察管理入口，不重放已完成的私有 sshd 配置解析。

使用既有 O_NOATIME/no-follow 稳定 reader，读取六份固定本地历史 ZIP，在内存中验证六个
archive pin、26 个固定 member pin，并重算 approved-input 使用的容量分量。
24 行 snapshot、12 行 delta、46 行 configured quota、placement 和 row-relation 的既有
size/SHA-256 pin 全部吻合。这是准确容量分量复核，不冒充完整 approved-input 重建或现场准入。

| 分量 | 行数 | bytes | inodes |
| --- | ---: | ---: | ---: |
| 历史 snapshot | 24 | 626790400 | 32113 |
| 后续 delta | 12 | 138412032 | 8064 |
| effective，即以上两者之和 | 36 | 765202432 | 40177 |
| 既有 configured quota 完整限额 | 46 | 249561088 | 17792 |

核对关系如下：

- snapshot 的前七行已经包含旧 reconciliation prefix，不能再叠加一次；effective 也不能
  与 snapshot/delta 再相加。计账实际使用 snapshot + delta 各一次。
- configured quota 是合同明确另保留的完整配额义务，不以当前已用量、未启动或 UNKNOWN 抵扣。
  本轮没有把这种已批准的保守计账改成退款，也没有发现以上固定向量的算术不一致。
- 03a、05a、05b 各保留完整核心承诺；05c 再计一次。下列数字复核的是已经消费的这四批，
  没有计入或授权第五次核心执行。05c 消费后也不释放其承诺。
- 同一义务涉及多个角色时，每个实际不同设备完整计一次；若角色共用设备，该义务在该设备
  只计一次。历史和新对象仍须通过实际 placement 核验，离线假设不能代替设备事实。

## 按角色分离时的准确需求

以下是 **system（state/install 同设备）、quota、journal、evidence 四池互不共用设备** 的
条件计算，不是 05c 实际设备映射或当前剩余量。较早历史列为 snapshot + delta；配额另列。

| 角色 | 较早历史 bytes | 既有配额 bytes | 三旧核心 bytes | 05c bytes | 要求可用 bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| system | 730599424 | 0 | 603979776 | 201326592 | 1535905792 |
| quota | 49283072 | 249561088 | 166723584 | 55574528 | 521142272 |
| journal | 153092096 | 0 | 110100480 | 36700160 | 299892736 |
| evidence | 167772160 | 0 | 289406976 | 96468992 | 553648128 |

| 角色 | 较早历史 inode | 既有配额 inode | 三旧核心 inode | 05c inode | 要求可用 inode |
| --- | ---: | ---: | ---: | ---: | ---: |
| system | 38129 | 0 | 36864 | 12288 | 87281 |
| quota | 8576 | 17792 | 23424 | 7808 | 57600 |
| journal | 3456 | 0 | 16512 | 5504 | 25472 |
| evidence | 3072 | 0 | 18816 | 6272 | 28160 |

每一核心批次的分离设备增量，分别为 system 192 MiB/12288、quota 53 MiB/7808、
journal 35 MiB/5504、evidence 92 MiB/6272。quota 不只是 21 MiB 的 21 根，还包含
8 MiB carrier wrapper 和三份各 8 MiB state wrapper 的逐设备保守预留。
system 含 64 MiB install、8 MiB carrier、24 MiB 三 case state，以及原 96 MiB admission headroom。
这些逐设备预留不是可消费预算；原 180 MiB/13440 physical、276 MiB/16512 admission 不变。

不能直接将分离设备表相加当成同盘要求。若所有角色共用一个设备，去重后历史承诺为
1882984448 B/107505 inode，05c 为 289406976 B/16512 inode，总要求为
**2172391424 B/124017 inode**。其它共盘关系依实际角色合并计算。
本轮枚举 state/install 同设备前提下全部 15 种角色设备分组，均得到一致核算结果。

## 已补齐的失败诊断

`_cap_charge` 原比较式和首个失败池立即停止的顺序保持。仅在该比较已经失败后，
用内存中已经算出的同一个 pool 生成 `CORE_CAP_INSUFFICIENT_...`：

- 固定角色组和原 dev/fs_uuid 的 SHA-256，不输出设备原值、UUID、路径或配置原文。
- bytes/inodes 的 AVAILABLE、HISTORICAL、NEW、REQUIRED，以及
  `DEFICIT = max(0, REQUIRED - AVAILABLE)`；共盘可用量仍取原代码已有的最小观测值。
- 负可用量使用 `NEG` 前缀；不合法的诊断字段退回原 `CORE_CAP_INSUFFICIENT`，不放行。

诊断最多 1024 个 ASCII 字符，通过未修改的 bootstrap `CORE_[A-Z0-9_]+` stderr 通道，
退出仍为 3。不增加 I/O、helper、文件、stdout frame、schema 或预算，不延长 deadline，
不继续扫描其它失败池。它不是实时容量修复，也没有补回 05c 丢失的数字。

## 验证和冻结

当前修复源码由引入本记录的 Git 提交定位；准确 dispatcher 为 454446/524288 B，SHA-256
`6b99e551d9e200f084ccabcf2a33b383bc1d1240f5f23149cd3f91c8953f060e`。
loader、bootstrap、业务 candidate、wheel、合同和空发行 allowlist 均不变。
bootstrap SHA-256 仍为 `7e2d08800951528c81f9078eb772cc4937dc76a3fd1ed7a1ccadde2a12a23cf5`。

- 新增 28 项回归，覆盖 bytes/inodes 单独或同时短缺、等号边界、共盘最小值、首池失败、
  大整数、负可用量、日志注入/无效字段以及真实 bootstrap 错误转发。
- 十个相关测试模块在普通用户权限、umask 022 下：**788 passed / 2 skipped / 11.93s**。
  JUnit SHA-256 `a34cd7d1ebd44df8abc6fcf5d7334d83135e25b7208731f586c97d2ad3525527`。
  首次沙箱运行 787 passed / 2 skipped / 1 failed：既有测试在 home 创建临时 fixture 时被
  只读文件系统拒绝。原失败报告保留，没有改测试、放宽保护或把失败算作通过。
- 使用真实固定容量分量，在 15 种角色分组下，与准确已发 D 的原 `_cap_charge` 进行
  141 组内存对照：30 组成功的全部返回值相同，111 组拒绝仍拒绝；独立分项求和也一致。
  这是算术/谓词兼容验证，不是模拟的实机成功。
- 私有离线审计脚本 SHA-256 `8e70c82813c5366f00d498af079f39ad727cb460af493c6d0d0092783c34ff07`，
  与原测试报告保留于本地 `lhqcore-capacity-review.RukSK8Mp`。`git diff --check` 通过。
  本轮未重跑完整本地 source/installed suite，未生成现场发行包；CI 状态以准确提交为准。

## 下一步只缺哪些现场事实

05c 原返回没有设备映射、可用量或差额，不能确定失败的是 bytes 还是 inode，
也不能判断是实际空间不足还是完整保留承诺造成门槛不足。host 260 MiB/72 条件不回答 guest 问题。

最小必要后续诊断应只取固定五个 guest parent 的设备角色对应、同一有界观察内的可用
bytes/inodes，并返回同一冻结输入下的历史、新增、总门槛和差额；不需要再运行 H01/Q4/H11、
重新采集 SSH 配置或读取业务结果。具体现场读取入口、准确候选、预算和一次性请求仍须另行
准备和批准，本记录不是可执行现场授权。若发现 placement 或配置配额已变，仍应停止，
不能以新数字自动采用新设备、清理旧对象、扩大容量或放宽阈值。

本轮不启动新现场链、不创建下一批，四旧核心及诊断的全额承诺和未知边界保留。
支线暂停，production `E3_SUPERVISION_UNVERIFIED` 保持。
