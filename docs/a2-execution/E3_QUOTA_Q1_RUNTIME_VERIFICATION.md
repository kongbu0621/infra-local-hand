# Q1 单次 systemd 查询装配：源码验证记录

被测源码：`39e7bcbbad388557cb1ebc3056c18f94a12bb1f4`；
tree `18520329f04a92c556c345928af09858c9d79bac`；
父提交 `8d283c9e939124175aea4c6cbf4afcd22f1ee0f0`。
本记录及日志另作后续提交，不把报告提交当作被测源码。

范围为 `LH-E3-QUOTA-HARNESS-v1`，批准 A `415327ebdcc251bb055da9931a7a88990f750b7a`、
独立 C `5a4ea852091db06549a876e42bbd5f95d5869d3b`。三份权威文档与 A 字节一致，
原生产 `E3_SUPERVISION_UNVERIFIED`、四包和 Plugin 未变。本次未新增安装、宿主准备或支持授权。

## 实现结果

已把 Q1 的内部判定核心连接到**单次 systemd 查询装配源码**，没有完成管理监听服务或实机验收。
详细接口和候选运行属性见 [管理侧 README](../../tools/admin/local_hand_quota_observer/README.md)。

- 新 worker 使用保护配置、固定安装摘要、准确 boot/user namespace/cgroup/InvocationID，
  在查询单元内部打开固定普通 UID/0700 根；核验同 namespace 的 mount ID、FS 类型/设备/rw，
  READY 后将同一根 FD 3 交给以验证 ELF FD 执行的 native。systemd-run 不承担任意 FD 传递。
- 固定 system-manager 命令禁 shell、pager 和密码提示，准确单元 Type/ExitType/Restart/KillMode，
  原剩余 wall 时间、有限内存/Tasks/CPU/输出；权限仅 root 查询所需的 CAP_SYS_ADMIN 与 CAP_DAC_READ_SEARCH。
  NNP 不冒充能力移除；固定 slot 保留 mount write access，符合 Q_GETQUOTA 的真实内核路径。
- 原生协议升为 `local-hand-quota-abi/v2`：真实查询前安装参数级 seccomp，绑定 FD 3 和已观察 project；
  查询、前后身份及即时 errno 保留。过滤安装失败不进入 quota；旧 v1 不被当作已有过滤证明。
- `StartJournal` 最多 32 个永久意图。文件与目录 fsync 后才交付一次；原 request/allocation/slot/root/domain
  不因失败、崩溃或换代次自动重用。0700 控制目录对 worker 不可见，受保护安装与根不得和它交叠。
- manager 尚未收到启动时有限等待；轮询为最终停止保留调用额度。先保留原 InvocationID/终态，
  再按相同身份停止，核验排队 job、原 launcher/control 退出及双 EOF。
  systemd 在 active/exited 时可清理叶 cgroup，因此从准确、预先保留的专用父 cgroup 证明后代树为空。
- 失败后尽可能停止已知原身份，保留首因、原始回包前缀、终态、记账错误和未收口进程。
  原 query 截止包含停止与双 EOF；额外 3 秒只供清理，不能转记成功。
  恢复没有原 InvocationID 就不停止当前同名单元；原采集归属丢失始终 UNKNOWN，不补投、不回收资源。
- CI 路径过滤加入管理侧源码目录，后续仅修改查询器也会触发验证。

## 本地验证

命令：`python3 -m unittest discover -s tests -p 'test_e3_quota_*.py' -v`。
最终结果 **106 项测试方法通过，0 跳过，退出码 0**；源码 compileall、暂存差异检查、
批准 A 文档不变和生产/分发代码不变检查均为 0。

| 测试组 | 方法数 | 证明范围 |
| --- | ---: | --- |
| native ABI / filter | 13 | 已编译 C；成功 quota 使用独立 syscall shim，真实 seccomp 仅执行无害禁止调用负例 |
| journal | 22 | 真实临时目录、文件/目录 fsync、锁、进程崩溃；交付 callback 为 LOGIC_ONLY |
| manifest / monitor | 15 | 精确协议/根/project/限制、管道与退出判定；manager 事实为 LOGIC_ONLY |
| runtime 状态机 | 17 | 真实解析/argv/监控代码配合假 manager/journal/clock/Capture，覆盖启动、停止、超时、丢失和恢复 |
| Capture / unit argv | 14 | 真实有限 Python 子进程、匿名双管道、EOF/进程退出独立检查；systemd argv 为静态逻辑检查 |
| parent cgroup / host | 8 | 真实临时 FD/events 文件的缺失、替换、格式、读错误；mount/boot/namespace 事实为 LOGIC_ONLY |
| worker / protected inputs | 17 | 真实 NOFOLLOW/有限读取/ELF/CLI 拒绝；部分所有权与身份、能力、exec 成功链为 LOGIC_ONLY |

开发联调中曾出现 native 已升 v2 而 Python 消费者仍预期 v1 的失败，已同步修复并加入旧版本拒绝负例。
该中间轮次只有会话运行记录，本报告不声称归档其逐字日志；最终通过依据是下列独立新运行的原始日志。
未执行本候选完整源码/安装套件；不沿用历史候选的全量结果。发布后的远端 CI 另按准确提交核验，
本记录没有提前声明 CI 通过。

## 仓库内证据

按照 Owner 的普通开发记录偏好，本轮**不生成 ZIP**。下列可公开证据与测试源码一并入库：

- [最终测试原始日志](validation/q1-runtime-20260923/unittest.log)：stdout/stderr 按实际输出顺序合并，无改写。
- [命令、时间、退出码和检查结果](validation/q1-runtime-20260923/commands.json)。
- [Python、编译器与架构](validation/q1-runtime-20260923/environment.json)。
- [准确源码提交/tree 与逐文件 SHA-256](validation/q1-runtime-20260923/source-map.json)。

本轮临时测试 binary 随测试目录清理，没有生成可安装管理产物，也没有宣称完整编译环境封存。
旧检查点私有 ZIP 保持独立历史记录；没有将其主机路径、账户事实或原始盘点内容复制到 Public。
真实主机验收、阶段冻结或正式交接才另行封存完整私有原件。

## 剩余边界与下一步

**真实 quota syscall 0；启动 systemd 单元 0；GX10 操作 0。Q1 实机与整体 E3 仍 BLOCKED。**

1. 专用环境须预先具备可丢弃 FS/普通 UID/固定 root/project/limit、持续保留的专用 slice/cgroup、
   树外独立受监督控制器、保护安装与有限本地 journal。当前没有创建或挪用这些对象。
2. UUID 仍是保护配置的映射，尚无独立真实 FS UUID 证明；系统库/loader 和控制器/journal 源码须由外层
   fixture 另行固定。installation_digest 不能冒充整个管理系统的可信证明。
3. 已有的 syscall filter 只覆盖 native 受信前奏之后，不消除 CAP_SYS_ADMIN 信任或 concurrent admin/writer 风险；
   仍须验证实际 namespace、能力、文件系统可达面、enforcement 和超限写入。
4. Q1 控制器不是 listener：配置读取、fsync、进程创建可能阻塞，必须受外部独立监督。
   `pending_clients` 空列表不能证明采集器全停；恢复中丢失原 launcher/pipe 归属不转为完整停止证明。
5. Q1 实测通过后再完成 Q2 鉴权通信/receipt/原 allocation 和三段预算绑定，继而 Q3 真实三单元正常链与 Q4 故障恢复。
   Q1 的永久意图 journal 不替代这些出口，也不启用现有生产路径。

下一步准备准确隔离 fixture 配置与 Q1 实测交接，当前不操作 GX10、不重复旧库存探针。
