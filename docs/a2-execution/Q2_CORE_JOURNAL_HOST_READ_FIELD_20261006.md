# Journal host-read：R2 完成与唯一替代窗口失败

日期：2026-10-06（Asia/Shanghai）。状态：**R2 已完成；唯一获批替代预检窗口已失败并关闭；R3 维护未开始。**
本记录只登记真实准备、验证和现场结果，不批准新的 host 特权入口、sudo 配置、窗口或维护动作。

## 准确链与发布状态

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本轮重新读取固定直接来源，SHA-256
  为 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- A：`2b4448c7b89d1910840f7aee2ae2b781f970e179`，`LH-Q2-CORE-JOURNAL-HOST-READ-v1`，R1–R3 only。
- 独立 C：`b5414d0cfd505b220ba4b68a454202f245c77f6c`。
- 实现 D：`8ce15f5786877e36c5983282b19a75d1439f6c47`。
- 本次实际完整候选：`c62319400c58e8ce067f0df150f8eb9ad0046719`，已非强制发布到
  `origin/main`；GitHub Actions `37423018921` 对该 SHA 完成且结论为 `success`。

原实现记录中的 0664 拒绝、沙箱资格失败和测试中间失败全部保留。本记录只更新之后发生的事实。

## 唯一输入权限修复与静态冻结

经本次交互明确确认，只把既有 `management_frame` 原文件从 mode 0664 收紧为 0600。
前后 device `66308`、inode `160457513`、uid/gid `1000/1000`、大小 `5496087` 均相同；
没有复制、替换、改写或删除原件。收紧后 SHA-256 为原固定值
`c9f4bb2744d48f9e7174157a95761d081be038cf4dd4f67ae42620a1a9e6d315`。

工具沙箱将 `/` 和 `/mnt` 映射成 uid 65534；在该环境直接调用固定 reader 曾于内容读取前返回
`LOCAL_PARENT`。这不是宿主不支持。真实普通宿主中这些父目录分别满足 root/当前 owner 资格，
同一 `freeze_growth_inputs` 随后读取准确 frame、plan archive 和六份历史 archive，结果：

- `source_count=8`，角色集合为 `management_frame`、`plan_archive`、`20260930b`、
  `20261001a`、`20261001b`、`20261001c`、`20261001d`、`20261001e`；
- `source_binding_sha256=2cb178702a4aedfc1b9366eab4d8e111f73d8130bf38be96460116ceebb14caa`；
- `plan_sha256=efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c`；
- `inventory_sha256=a5ea03d6311884a8ff47244271b3ccfecc18d934db9ca66172668cf8078851fd`；
- `description_sha256=64c6cfc7b773aa51af33cf971da672786c49965e16cc75923fc6fc25b1ac4814`；
- `horizon_sha256=3ecc6bd649d4e33bdc08283c8b76984fad286a1b484f7df0452b59a470033c82`。

第一次直接 Python 导入因没有加入仓库 `tests` 模块路径而在构造 `Inputs` 前失败；修正模块路径后，
沙箱调用出现上述 `LOCAL_PARENT`。两者均未建立 `Window`、未调用 sudo、未读取不合格内容，
也不是现场窗口或 observer 重试。

## 精确候选 J2 验证

对完整候选 `c62319400c58e8ce067f0df150f8eb9ad0046719` 重新执行 `growth_sources` 和固定 payload 生成：

- 12 个源码成员通过，host/guest 两个实现分别 `65434` / `65280` 字节；
- 内核 reader SHA-256 `947469560ca3bdc4997a56739b42561c4a616a5dc8b250b919db589689eecc02`；
- loader SHA-256 `081d3bed41e9f49153096cb893ee20980182831d551c41b9504b886fd0c46aca`；
- 绑定该完整候选的 root payload 为 `23707` 字节，SHA-256
  `02eaf61b923682a8ab31749ab7fc0e0e51f90aeefe05ede4834cea5bb6d40b32`。

在真实普通宿主重复九文件窄测：**395 passed，0 skipped，2.59s**。`git diff --check` 通过；
候选 CI 如上为成功。未以旧 CI、沙箱 SKIP 或 mock 替代这些结果。

## 唯一替代预检窗口的真实结果

全部离线门通过后，按 A 启动固定 `lhqjgrow-20261006a` 的唯一替代预检窗口。
预检只到第一个 root writer observer：固定 `/usr/bin/sudo -n -- /usr/bin/env -i ...`
返回非零，入口以 `GROWTH_WRITER_FAILED`、`BLOCKED`、退出 3 停止。

安全摘要：

- CLI stdout `531` 字节，SHA-256
  `bb30331e62ee075f3f36056dc880b17a17490374d5cb360631a757ccfe3a780d`；CLI stderr 为空；
- writer report `0`；marker `false`；SSH requests `0`；
- 2026-10-06 15:16:40 +08:00 的既有 sudo 审计事件明确包含 `a password is required`，
  对应命令事件摘要为 `114872ff848ab953a23b920a2fd9e0a9ad357d455bf5766ac8625dec303496fb`；
- 审计没有 authentication failure 或 incorrect-password 信号。没有再次调用 sudo 或 observer；
  后续只对既有 journal/auth log 做计数、时间和摘要读取，没有输出完整命令或私密原文。

这证明实际 host 普通执行身份没有获得当前 A 所假定的 NOPASSWD 固定 observer 准入。
guest cloud-init 中 `q1admin` 的 grant 不能外推为 host 普通账号权限；也不能把密码提示描述成
root payload 已运行或 writer 扫描失败。

## 精确计数、停止边界与下一入口

本次真实计数：替代窗口 **1（失败、关闭）**；sudo 请求 1；root payload 执行 0；writer report 0；
marker 0；SSH 0；关机 0；备份 0；镜像增长 0；VM 启动 0；ext4 增长 0；H01/Q4/H11 0。
没有业务执行、扩容 receipt 或结果证据。输入权限保持 0600，不回退；其它现场状态未清理或修改。

当前 A 明确规定新预检失败即停止，不能再次开启同一入口。以下任一项都是 material change：

1. 新增或修改 host sudoers、账号、能力、root-owned helper、服务或其它系统配置；
2. 改变固定 observer argv、信任边界、输入协议或可见性判定；
3. 新增 host privileged carrier 或把 guest grant 当成 host grant；
4. 再给一次窗口、observer、marker、SSH 或维护机会。

因此受影响的后续 R3 保持 OPEN。若继续，必须先给出准确三层文档，明确 root 入口的安装/调用、
最小权限、一次性状态、预算、审计、失败保留和卸载/保留边界，再由 Owner 基于新 A 明确关闭。
在此之前不得探测 sudo、重跑 observer、修改 host 配置或执行维护。namespace/watchdog 继续暂停，
production `E3_SUPERVISION_UNVERIFIED` 保持。
