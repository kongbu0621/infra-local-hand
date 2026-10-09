# 运行时准备与原核心接续：已批准基线

**CLOSED for RT1–RT3 only**，`LH-Q2-CORE-RUNTIME-CONTINUATION-v1`。
R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`及其直接来源、完整性、Owner mandate/authority、
无例外和实质变更规则保持。Owner B见[准确决定](Q2_CORE_RUNTIME_CONTINUATION_OWNER_DECISION.md)，
事件 `LH-Q2-CORE-RUNTIME-CONTINUATION-CLOSURE-20261009-01`。

A `dc6e6c511936e02f41cda0cf86cbd571f3aa253d`，tree `01fa3c68860a2e5106e9d3e59fdb1b9efe63d7b1`，
父提交 `93227cf3c859d1f8fbda78f5123d9102f8ced3ad`。A仅含三文档；历史OPEN标签不改，
以本准确B/C关闭该范围。普通路径修复93227cf首次CI 37921156348为3/3，Linux7233/89
skipped、Windows1809/1357 skipped、独立安装94 checks/292 commands；不替代RT1验证。

| 文档（docs/a2-execution/q2-core-runtime-continuation/） | bytes | SHA-256 |
| --- | ---: | --- |
| ARCHITECTURE.md | 9008 | 97e44b405a8c7b89e116e7578c81f6ce97f2f85e2950c6aaa9cdef1e0b386b63 |
| IMPLEMENTATION_PLAN.md | 5064 | bfb3d448210c01cff0fdae3088eb5f90ea19d978df842b6c773234c5bff40b78 |
| REQUIREMENTS.md | 5438 | 35311cf40446b9e87047e74fcb4cbc04c31e6b088c0db382a34d8c789e952448 |

独立C只登记闭合。D继承C，不squash；RT1完成两端实现、真实来源/包上限/费用验证、
准确D发布/CI/独立安装及双方caller冻结后才可RT2。RT2仅09b，完整成功后才可RT3。
当前RT1 NOT_STARTED，RT2 NOT_ISSUED，RT3/H01/Q4/H11 NOT_RUN。十一代维护加原核心
捕获的宿主底线为14320 MiB/4086 inodes，原所有硬限额保持。新运行时成本依A另行归入
对应guest pool，不退款。旧十个窗口保持消费，失败停止，不自动再开窗口。

## 仅获准公开的旧09a最小索引

准确旧D `54d32df2f82fe863e1535ddb8134617c2654e33d`，私有核对事件
`VA2-09A-ORIGINALS-INDEX-REVIEW-20261009-01`。以下内容已与原私有索引及保留原件一致核对。
只允许本表三列公开，其它原文/元数据仍私有。

| basename | bytes | SHA-256 |
| --- | ---: | --- |
| .lhqjgrow-20261009a.consumed.json | 59556 | 777715c3cbf6d9c9ecef43a63ae1fe2dee6fa4c48170f0114aa883383f55c87d |
| .lhqjgrow-20261009a.events.jsonl | 441 | 687cce89ef1ef88e44d482655d61e2a8e48d84bb4e2da36d154ccf98accfec60 |
| .lhqjgrow-20261009a.pre.stderr | 922 | 6c40a4e9d0882c80ffb89829be5c52cf9bc861a698d5bd498c1efa434539a88e |
| .lhqjgrow-20261009a.pre.stdout | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| .lhqjgrow-20261009a.receipt.json | 16482 | 1737c6c75c8dc97b80734e94b4d161f33b9893d7ad8e63658acc9514e190d096 |
