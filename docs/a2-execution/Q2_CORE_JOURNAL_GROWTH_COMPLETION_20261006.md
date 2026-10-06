# Journal 维护流程接线与本地交接

2026-10-06。**J1 主流程已接线；本次窄验证 309 PASS / 2 SKIP；完整 J2 仍待现场工具/输入冻结与原生验证，J3 NOT ISSUED。**
没有扩容成功或 H01/Q4/H11 通过的声明。两项 SKIP 不能折算为 PASS。

继续既有 `LH-Q2-CORE-JOURNAL-GROWTH-v1` J1–J3：R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，
A `59948ec4fedb807a31cdbff77acc134e84414160`，Owner B 事件
`LH-Q2-CORE-JOURNAL-GROWTH-CLOSURE-20261006-01`，C `6493b1ae035dfa852952165046417c78f0f5383c`。
本实现基于 `8e91fa2631aa18a8469efa5a14e4145eaf781e28`；A 三文档、生产实现与旧核心 boot 校验均未修改。
本文件随实现提交；执行时必须使用该准确实现提交并通过 `--expected-commit` 校验。

## 本次完成

- 从固定 frame/P、原 archive 两个固定成员、六个历史 archive 和固定管理原件形成完整输入清单。
  不执行旧 runner，也不搜索替代来源。四份 HELLO 与已保存五目录容量绑定到当前描述。
- 接通 marker → 第一阶段静止/持久性/设备/工具/内容检查 → 回收并 fsync 前报告 →
  单次绑定令牌 → 正常关机 → 原 pidfd 退出/镜像无 writer → 完整备份 →
  单次镜像增长 → 单次原配置启动 → 被动 60 秒 → 第二阶段 ext4 增长/内容与容量核对。
- 保留严格 unit、cgroup、process、启动关系、UUID、virtio serial、inode、文件权限与路径校验。
  未知间接启动关系、不可读进程、额外 writer、证据仅存 tmpfs 均拒绝；不通过停用业务制造静止。
- 两条 SSH 分别保存原始 stdout/stderr。前报告未落盘、后阶段描述超限或报告绑定失败时，
  不发送关机令牌。没有探测连接、自动重试、自动恢复或第二次启动。
- 修复扫描器自身短暂 FD 导致的必现误报；保留原 QEMU 裸程序名 argv[0]，
  启动仅改变已批准的 pidfile/serial，执行文件仍由受保护 FD 绑定。
- 异常结果保留已有 PID/启动标记、流摘要、已开始步骤与 UNKNOWN；不向 mutator 发终止信号。
  拒绝会强制杀死 mutator 的继承 CPU/文件大小限制，未关闭这些限制继续运行。
- 预检与执行绑定同一双时钟起点和管理主机 boot ID，第二次调用不能刷新 900s 窗口；
  缺失、过期、未来起点或主机重启都在现场输入/marker 前拒绝。
- 两个实现文件分别为 64744 B / 64589 B，低于各 65536 B 上限；只读通用原语共享于原两个模块，
  未引入第三模块或依赖。host 使用两空格缩进；格式变换经 AST 等价检查。

## 验证与实际限制

Python 3.12.14；`git diff --check` 通过。执行以下范围：

```sh
python3 -B -m pytest -q -rs \
  tests/test_e3_q2_journal_growth.py \
  tests/test_e3_q2_journal_growth_host.py \
  tests/test_e3_q2_journal_growth_guest_completion.py \
  tests/test_e3_q2_journal_growth_inputs.py \
  tests/test_e3_q2_journal_growth_transport.py \
  tests/test_e3_q2_journal_growth_coordinator.py \
  tests/test_e3_q2_core_capacity_observation.py
```

结果 **309 passed, 2 skipped**。SKIP 原因：云端执行进程 PID 与可见 `/proc/PID` 映射不一致；
云端缺少原生 qcow2/ext4 合成 fixture 工具。没有修改实现来容忍这些条件。
已覆盖实际 coordinator 的完整顺序、每个效果失败后停止、清单不匹配零写入、
后描述超限先于关机、超时封存仍保留已知进程、独立管道与 nonce 协议等。
首次回归发现的源文件上限、原生测试环境映射与新增资源限制测试替身问题均已针对性修复。

旧组件提交 `780023e34368cc3a7d91276e19e859ec13603014` 的
[CI 37408293031](https://github.com/kongbu0621/infra-local-hand/actions/runs/37408293031) 已核对成功；
这不是本次新提交的 CI 结果。本次相关 CI 需按新提交另行核对。

不能从合成测试推断真实 host 可穷尽 writer：普通账号若读不到其它 UID 的 `/proc`，
本地预检在 marker 前以 `GROWTH_WRITERS_UNKNOWN` 停止，附 PID/TID/errno/path 诊断。
不得跳过其它用户、忽略消失 FD、添加 sudo fallback 或改变权限以把 UNKNOWN 变成 PASS。
guest 对无法分类的间接自启动行为保留具体 unit/manager 诊断，不能假装已静止。

CPU/RSS 是部分观测，guest 回报之后的开销与跨 host/guest 聚合仍为 UNKNOWN；不宣称完整硬资源隔离。
host 的 900s 双时钟与 780s 新动作截止始终使用原起点。guest 相对窗口不能证明 SSH/PAM
延迟后的精确 host 时钟起点；不将它表述为远端 syscall 的硬期限或超时即退出证明。
已开始的 mutator 可能越过观测期限，保留 UNKNOWN、停止后续动作。

## 给本地 Codex 的下一步

继续同一已批准范围，不重复申请 A、不重装、不清理、不进入支线，也不运行旧 consumed 入口。

1. 使用本次干净准确提交 D，核对其相关 CI。先在独立合成 fixture 运行上面窄测试；
   原生 pidfd 与 qcow2/ext4 两项必须实际通过，不能以 SKIP 或云端 mock 代替。
   没有既有工具就停止并报告，不在原 VM 临时安装。
2. 复用现有准确 frame、原 plan archive、六个历史 archive 所在目录。
   将既有记录中的真实路径分别代入 `FRAME`、`PLAN_ARCHIVE`、`ARCHIVES_DIR`；不猜路径或搜索替代副本。
   只执行本地清单核对，不带 `--execute`：

```sh
python3 -B tests/e3_host/q2_journal_growth.py \
  --expected-commit "$D" --frame "$FRAME" \
  --plan-archive "$PLAN_ARCHIVE" --archives-dir "$ARCHIVES_DIR"
```

这一步不创建 marker、不发 SSH、不改镜像。输出是私有执行清单、`manifest_sha256` 和 `window_binding`，不得公开其中机器信息。
首次现场预检仅运行一次；执行必须原样继承其 JSON `window_binding`，不能重跑预检获取新起点。
预检失败也保留已知窗口；重核对只能显式传入同一绑定，过期则停止。
marker 前没有新的持久文件，程序不能证明调用者没有丢弃原预检结果另开首次预检；不得把这一管理信任描述为硬防重启保证。
工具身份/版本、完整原/新 argv、所有输入与镜像身份必须与已审阅清单一致。
如果可见性、原件、预算、工具或身份核对失败，交回首个具体诊断；不能消费维护机会试探。

3. 只有全部必要 J2 检查实际通过且没有新的 material 差异，才使用该摘要执行同一固定会话一次：

```sh
python3 -B tests/e3_host/q2_journal_growth.py \
  --expected-commit "$D" --frame "$FRAME" \
  --plan-archive "$PLAN_ARCHIVE" --archives-dir "$ARCHIVES_DIR" \
  --expected-manifest "$MANIFEST_SHA256" --window-binding "$WINDOW_BINDING_JSON" --execute
```

摘要参数是准确清单绑定，不是用户自报“已通过 J2”的授权替代。
marker 保存完整清单、nonce、时钟及实际第一阶段命令摘要；第二阶段按固定源码算法嵌入已落盘前报告，
其实际 argv 摘要在发出前入 events。不得声称尚未收到前报告时已知道第二阶段全部动态字节。
任一目标文件已经存在即停止；不删除文件、不换 session、不自动重试。

完成后只交回 receipt、两个阶段原始日志与前后容量/boot/备份摘要；失败则交回首个失败与已发生修改。
此时才依据实际维护结果接回核心验收准备，不能提前改旧 boot 校验、填新业务 ID 或宣布 H11 通过。

本次云端现场计数：marker 0、SSH 0、关机 0、原镜像备份/增长 0、VM 启动 0、H01/Q4/H11 0。
`lhqjgrow-20261006a` 未消费。原有 UNKNOWN、保留承诺与 production `E3_SUPERVISION_UNVERIFIED` 保持。
