# 核心原单次 F1：真实管理请求失败与接线修复

2026-10-05 +08:00。**原唯一 marker/request 已消费，STOP_AND_RETAIN；不能重试。**
真实管理通道取得有效 HELLO；尚未发送 BIND/package，未进入正常任务提交阶段，没有业务结果包。
原 receipt 两项业务 truth 保持 UNKNOWN。namespace/watchdog 暂停，production E3 保持。
批准、独立 C、固定 cloud-init 修复及发行前审查见
[G1–G3 复核](Q2_CORE_CLOUD_INIT_GRANT_BINDING_REVIEW_20261005.md)。

## 准确发行 D 与测试

发行 D `605a2a38d1db5ef85c961b4d357cafa157bdd7d5`，tree
`ced38519fe6e3b86973de5ccf0dff60fc62322e4`。三个 field 文件与 `0293c46` 逐字相同。
[CI 37218627924](https://github.com/kongbu0621/infra-local-hand/actions/runs/37218627924)
在 F1 前已 3/3 success；Linux 完整源码 **4940 passed / 88 skipped / 439.09s**，独立安装
**94 checks / 292 commands**。前一 D 的 CI 37217961194 也已 3/3 success。

本地同一 D 的完整源码首次为 **1 failed / 4901 passed / 126 skipped / 451.08s**：
`test_real_kernel_reader_bound_and_numeric_proc` 触发 `RECON_KERNEL_ANCESTRY_CHANGED`。
它检查 `/proc` held ancestor 的 device/inode/mode/uid/gid/nlink 稳定性；失败栈未记录具体漂移字段，
不能臆定字段或推断 guest 不支持。没有改断言或放宽 reader。保留报告
`lh-core-release-source.V56cA3/source.xml`，SHA-256
`80f62d42fac916d26514a81cad906188f2e3dac6cab72f454b05ef2ffb265cba`。
同组隔离检查 35 passed；随后定向命令一次遗漏 `umask 022`，在实际 `0002` 下为
23 failed / 1003 passed / 35 skipped：测试 fixture 组可写，被原保护条件拒绝。
恢复原测试准备后，同代码/断言 **1026 passed / 35 skipped / 18.06s**，报告
`lh-core-release-source.V56cA3/targeted-correct-umask.xml`，SHA-256
`c9ed6ea8be1abf5393a3dc254372c6c0bc0024f005d014c78c7abf918bc0b73f`。
保留失败；完整源码通过证据来自同一 D 的独立 CI，不用定向 PASS 替代完整运行。

本机独立 clone/install 同一 D 也 PASS，94 checks / 292 commands；报告
`lh-core-release-installed.mb7x7g/acceptance/report.json`，SHA-256
`3ed4159d1c2b232f3652391a7b52dbefdf0c02e4cc52e843787078a740d6c9d3`；测试 wheel SHA-256
`1d0351d7c3ba463ef9adf8d24be8862fc4ea653ce70255022180f55c6abb1e59`。
现场仍用原批准 candidate/wheel/projection，未更换。

## 实际包、唯一消费与停止位置

发布门通过后，同一 live caller 从静态和私有源开始，重新取得原 900 秒双钟 origin、held
anchor/writer/原件，再两次 build/parse；未复用旧审查包或结束 caller 的 writer/window。
实际包 **18111397 B / 860 members**，SHA-256
`a8ca34f3fba3fd370485b522f3c009fa41de70fab1441224b56232885b77380e`；manifest SHA-256
`9c05d55ed52dc1e0c04ad340549de6e584a4296b392d84abd07428f179a1989f`；approved-input SHA-256
`576e456270ed0253c786c600497ac486c56cb3ece8930ff88a0ac54daea8eee2`。
本地重验固定 marker/五个 output absence 后，原 O_EXCL marker 完整创建、fsync/回读，
**一次 carrier execve 成功，真实 HELLO 验证通过**。这不是从工具环境 PID 1 推断宿主能力。

随后 host `build_bind()` 拒绝 `CORE_BIND_PACKAGE_ENTRY`：准确 v3 package entry 含 `writer`，
该函数旧 strict keyset 漏掉它。保留的 `CORE_TRANSPORT_FAILED.detail_sha256`
`3f9d2c41bee8fd7e5d9e8fbde450524e26d72c54065d5f0a158656d24c7e569d`，与 canonical
`{"reason":"CORE_BIND_PACKAGE_ENTRY"}` 的独立 SHA-256 完全匹配。

实测 `hello_valid=true`；`bind_written=false`、`package_written=false`、
`stdin_bytes_written=0`、`stdin_eof=false`。SSH wait status 255，stdout/stderr EOF 与
host_deadline_met 均未证明。host 停止并保留，未发第二 request、未重连、未查询或重启远端 unit。
**远端退出闭合仍 UNKNOWN**，不能将 SSH 退出当作远端监督完成。
依据零 BIND/package 与固定 bootstrap 顺序，H01/Q4/H11 未进入任务提交阶段；无业务结果包。
原 receipt 的 `real_task_execution`、`result_evidence_collection` 均 **UNKNOWN**，原样保留，
不合成成功、REMOTE_STOP_AND_RETAIN 或不存在的业务结果。

原 live finalizer 返回 STOP_AND_RETAIN：logical bytes 9318、created inodes 5、max observed
allocated bytes 16384，`full_filesystem_peak_proven=false`。只创建原六名中的五文件，
remote-result 缺席。后续只读摘要核对不是新增 live 及时性证明。

| 原固定文件 | bytes | SHA-256 |
| --- | ---: | --- |
| `.lhqcore-20261003a.carrier-consumed.json` | 3577 | `5d85f8d5c51329bf46eba91d0106a41d449389e16b018bbb30ddbc667e69d502` |
| `.lhqcore-20261003a.stdout` | 2852 | `bd042a224271b03eadaddb99868e3f0c4cef4f71365482f112577005d8be5e1d` |
| `.lhqcore-20261003a.stderr` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `.lhqcore-20261003a.capture-manifest.json` | 1637 | `5ab260b4062404991151dd917fd636d4f1cd4ba5dd0ffa45a1578f5cf6bb3db3` |
| `.lhqcore-20261003a.acceptance-receipt.json` | 1252 | `dd1d4f5c607572fa9eb1527ddb94e2eb839f5ae5e59509042b6d03313cf74700` |

原私有管理 anchor 保留文件；raw HELLO、机器路径/身份和 key 不入公共仓库。
未安装新的 guest candidate、创建 case ledger、取消或恢复任务；无清理、配置变更或预算退款。
这是一次真实管理请求失败，不是真实业务任务链通过。

## 原开发范围内修复与剩余边界

在原 CLOSED writer/核心开发范围内，BIND strict keyset 接入原 v3 `writer` 并显式调用原
`validate_local_writer`。不变更 wire 字段/版本或身份规则。测试 fixture 不再漏掉 writer，
与实际 package `ENTRY_FIELDS` 对照，并拒绝未知字段、缺失 writer 或 credential 不一致。
修正后的 window/BIND 和本地真实 OS pipe（对端显式模拟）回归在旧 `605a2a3` 源上为
**2 failed**，复现零输入发送；修复后 entry/freezer **82 passed / 3.35s**。
模拟仅作失败回归，不作现场 PASS。

原唯一 marker/request 已消费；源码修复不赋予第二次执行或刷新 deadline 的权限。
当前 release allowlist 重新置空，marker 不删除/改名，不发行修复后的现场包。
先冻结修复 D 并验证；若后续需要再验收，必须先形成新的准确批次 A、Owner B 和独立 C，
处理本次失败、未确认退出和保留义务。不得复用旧批次、另开探针或直接启用 production E3。
