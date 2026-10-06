# Journal 本机终端认证 Owner 决定

本记录保留 Owner 对准确 A 的决定，并关闭
`LH-Q2-CORE-JOURNAL-TERMINAL-AUTH-v1` 的 T1–T3。它不是实现、测试、sudo 认证或
journal 扩容成功的证明。

- Authority：当前本地 Codex 对话中的本仓库 Owner。
- Event：`LH-Q2-CORE-JOURNAL-TERMINAL-AUTH-CLOSURE-20261006-01`；登记日期
  2026-10-06，Asia/Shanghai。
- 稳定来源：本对话紧接[准确请求](Q2_CORE_JOURNAL_TERMINAL_AUTH_BASELINE.md)之后的
  Owner 回复；下文逐字保留，不补造消息时间。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本执行者已重新完整读取直接固定规则，
  SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- A：`2b236865dc0a89e475c4021cac44d7193f252f67`，tree
  `3150bd79d0f996c6ab7f07df0965848284ee5a9e`，parent
  `c62319400c58e8ce067f0df150f8eb9ad0046719`；三文档摘要由准确请求固定。
- 现场失败记录：`7fd8a1effe8fea144a0735a62c83745a08a34b9f`。准确 A 分支与该记录经
  `3da7ffce3db46fa3e1a8162cdb775c2d74a91246` 保留双亲汇合；未重写或 squash A。

## 准确批准

> 按原 R，批准 A `2b236865dc0a89e475c4021cac44d7193f252f67` 的 `LH-Q2-CORE-JOURNAL-TERMINAL-AUTH-v1`，关闭 T1–T3 范围 Gate；允许本人在本机真实前台终端为固定只读 writer 直接完成 sudo 认证，并替代本次未创建 marker 的失败预检窗口一次。先独立 C 再实现，保留原检查、15s/900s/780s、预算和累计维护次数；不修改 sudoers、不安装 helper、不整体提权，不自动重试、清理或扩展支线。

## 独立关闭及限制

本提交是 bookkeeping-only CLOSED C：只登记决定和 Gate 状态，不含源码、测试、可执行原型、
依赖、系统配置、release digest 或现场调用。A 的三份文档及其历史 OPEN 标签保持原字节，
实施 D 必须为本 C 的后继且不得与 C squash。

T1 仅可改变固定只读 writer 调用的终端认证接入；T2 必须完成准确候选、受影响窄测及相关 CI。
只有全部门通过，Owner 本人在真实本机前台终端就绪后，才可开始一次 T3 的新 900s/780s
替代窗口。Codex、程序、文件、参数、环境和日志不得接收密码；不得使用 `-S`、`-A`、askpass、
sudo-v、独立 sudo 探测或先 `-n` 后交互的 fallback。

原每检查点 15s、最多八个 writer 调用、一个 marker、两条维护 SSH、一次正常关机、备份、
镜像增长、VM 启动和 ext4 增长的累计上限及全部资源预算不增加。失败即停止，不重试、重连、
补采、强制关机、自动回滚或清理。不修改 sudoers、账号、capability、服务或安装 helper；
不批准 H01/Q4/H11、namespace/watchdog、production E3 或其它支线。
