# Journal 终端认证：唯一替代预检窗口结果

日期：2026-10-06（Asia/Shanghai）。状态：**T1/T2 已完成；T3 唯一替代预检窗口已失败并关闭；维护未开始。**
本记录只登记 Owner 本机真实前台终端返回的安全摘要、停止边界和后续证据保留修复；
它不批准新的 sudo、writer、marker、SSH、维护窗口、清理或业务执行。

## 准确链与候选

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- A：`2b236865dc0a89e475c4021cac44d7193f252f67`，
  `LH-Q2-CORE-JOURNAL-TERMINAL-AUTH-v1`，T1–T3 only。
- 独立 bookkeeping-only C：`12f7acac3b09fc5bd9344473ec930646c87e0f59`。
- 实际 T3 候选：`202c70a15c0e52940d8544c3ae3c41e0b57ebaec`，直接承接 T1 实现
  `cf34a53` 的测试可移植性修复。该候选已非强制发布到 `origin/main`，GitHub Actions
  `37440630131` 对准确 SHA 成功。
- T3 后的证据保留修复：`ac08b519f741b301f37959808749cb9755359123`，已非强制发布到
  `origin/main`。它没有参与已结束的 T3，也不改变该次现场事实或返还窗口。

执行前，真实普通宿主对准确 T3 候选完成 **400 passed** 的窄验证；静态八输入重新冻结，
`source_binding_sha256=2cb178702a4aedfc1b9366eab4d8e111f73d8130bf38be96460116ceebb14caa`，
计划摘要及历史 inventory/description/horizon 摘要与上一份 host-read 字段记录一致。
工具沙箱的 `/`、`/mnt` 身份映射不代表真实宿主，未被当作现场准入结论。

## 唯一 T3 窗口返回

Owner 在现有本机真实前台终端运行固定入口；shell 先核对 `HEAD` 和 `origin/main` 均为
`202c70a15c0e52940d8544c3ae3c41e0b57ebaec`，并核对终端为真实 tty。终端显示一次
`Sorry, try again.` 后再次提示；口令只交给 sudo 的终端界面，没有进入程序参数、环境、文件、
管道、日志或本记录。随后同一次调用结束，安全摘要为：

```text
LH_Q2_T3_SUMMARY={"child_checkpoint":1,"child_exit":3,"errno":null,"error_type":"ObservationError","exit_code":3,"marker_created":false,"phase":"preflight","reason":"GROWTH_WRITER_FAILED","ssh_requests":0,"state":"BLOCKED","transport_count":0,"writer_report_count":0}
```

Owner 随后只从同一 shell 已保留的 `PREFLIGHT_JSON` 打印 `diagnostic`；这没有再次调用程序、sudo、
writer 或现场对象。去除瞬时 child PID 后的安全诊断为：checkpoint `1`、exit `3`，stderr `0` B，
SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`；stdout `648` B，
SHA-256 `a56d810d1be3a13e21fe33892f43f407b0530da561836609780a258008944e74`。仓库不保留瞬时
PID 或 stdout 原文。该诊断证明非空 stdout 已到达父进程，但仅有长度和摘要，不能据此验证其 schema、
request 或具体 reason。

因此可证明：

- 唯一替代窗口已实际开始，并在第一个只读 writer checkpoint 返回 exit 3；入口以
  `BLOCKED` 停止；
- marker 未创建，SSH 请求和 transport 均为 0，writer 成功报告为 0；
- 没有进入正常关机、备份、journal 镜像增长、VM 启动、ext4 增长或内容/容量复核；
- H01/Q4/H11 没有执行；没有业务结果、扩容 receipt 或核心验收证据。

终端摘要不能证明第二次认证是否构成完整授权，也不能证明 root writer 在哪个内部条件失败。
不得把它提升为“认证成功”“认证失败”“容量失败”或其它更具体结论。

## 丢失的精确失败原因与修复

执行后复核发现，实际候选中的 `WriterProtocol.observe()` 对所有非零 sudo/writer child exit 都直接
改写为 `GROWTH_WRITER_FAILED`，没有区分“root writer 返回了有效有界失败 JSON”和“sudo 或子进程在
该报告之前失败”。因此现有安全摘要和补充诊断只保留 child exit、checkpoint、外层计数及 stream
长度/摘要，没有可解析的 stdout 原文；**本次首个具体下层原因不可由已留结果恢复，保持 UNKNOWN**。
不得根据源代码可能的失败集合、sudo 提示、648 B 长度/摘要或后续离线检查猜测原因，也不得声称
root payload 已经执行。

提交 `ac08b519f741b301f37959808749cb9755359123` 将未来非零 writer 返回限制为准确固定 schema，
严格校验 request、`complete=false`、有界大写 reason 和 errno 后保留具体 reason；缺失或畸形返回拒绝为
`GROWTH_WRITER_FAILURE_REPORT`。新增回归验证具体 `GROWTH_WRITER_DEADLINE` 不再被覆盖，且同一
checkpoint 仍不能重试。该修复没有调用 sudo、没有读取现场、没有创建 marker，也没有恢复本次
无法判定的下层原因。

修复后的真实宿主十文件窄测为 **401 passed，0 skipped，2.63s**；`git diff --check` 通过。
GitHub Actions `37445246001` 对准确 `ac08b519f741b301f37959808749cb9755359123`
完成且结论为 `success`，Linux 与 Windows job 均通过。冻结对象为：

| 对象 | 字节 | SHA-256 |
| --- | ---: | --- |
| `q2_journal_growth.py` | 65535 | `549a9785c9e87eb88a64227eadae26e7149121fe63c7bea1eb41d7bec4309470` |
| `q2_journal_growth_guest.py` | 65359 | `fe43c7858629a2109e7c40658acb58c685f13bef7befc5a86537baa317f20683` |
| `q2_host_kernel_facts.py` | 15055 | `947469560ca3bdc4997a56739b42561c4a616a5dc8b250b919db589689eecc02` |
| `q2_sshd_source_reader.py` | 8656 | `68c594cedbea15768789690b4afd0797bfff1057760a522f931e16a4a7ca3108` |
| root writer payload | 23707 | `21ca2ce653d8b45085750fce3b857e5180803475530c171e8127813dfd11c707` |

## 关闭边界

跨本次 T3 的准确现场计数为：替代预检窗口 1（失败、关闭），checkpoint 1，marker 0，SSH 0，
transport 0，关机 0，备份 0，镜像增长 0，VM 启动 0，ext4 增长 0，H01/Q4/H11 0。
认证尝试及 sudo/PAM 审计属于已披露管理副作用；没有自动清理。

A 明确规定失败即停止且不重试、不重连、不补采、不清理。本次未创建 marker 不返还窗口，
证据保留缺陷也不构成再次调用理由。任何新的 preflight、sudo writer、marker、SSH、维护窗口或
失败原因补采都需要新的准确 A、Owner 决定和独立 C；不能以 `ac08b51` 的修复或 CI 代替授权。
namespace/watchdog 与支线继续暂停，production `E3_SUPERVISION_UNVERIFIED` 保持。
