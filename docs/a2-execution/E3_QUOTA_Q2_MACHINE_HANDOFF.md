# Q2 现有实验机一次性交接

Q1 的原隔离 guest 范围已按 [收口复核](E3_QUOTA_Q1_CLOSEOUT_REVIEW.md)和
[容量模型复核](E3_QUOTA_Q1_GUEST_CAPACITY_REVIEW.md)完成；本入口不重做 Q1。
它补齐第八批完整 fixture 前检之前的现场资料收集步骤：没有完整 Q2 fixture 时，
也可以一次导出明确选择的现有 Q1 安装事实，供下一批装配核对使用。
范围为已 CLOSED 的 `LH-E3-QUOTA-HARNESS-v1` 隔离开发；不是宿主 provisioning 或生产准入。

## 唯一新增入口

[`tests/e3_host/q2_host_export.py`](../../tests/e3_host/q2_host_export.py)
是可通过 stdin 传入原实验 VM 的标准库脚本。它不导入已安装应用，不运行其中的程序，
不执行 shell、systemctl、quota syscall，不创建用户、目录、unit 或 fixture。
只读导出到 stdout；接收端保留私有 JSON，勿将原始宿主记录提交公共仓库。

必须显式提供以下三项，源码没有私有宿主默认值：

```sh
python3 -I -B q2_host_export.py \
  --q1-root "$Q1_EXISTING_INSTALL_ROOT" \
  --q1-revision "$Q1_EXISTING_REVISION_FULL_SHA" \
  --expected-hostname "$Q1_EXISTING_GUEST_HOSTNAME"
```

由已有 SSH/管理入口在原隔离 VM 内执行，使用现有 root 读取权限及独立有限超时。
`-I -B` 是必要条件。脚本先核对 Linux、root、显式主机名、systemd PID 1、
QEMU/KVM DMI 提示及初始 user namespace，然后才读取受保护安装。
这些是与声明相符的 guest 提示，不是密码学宿主身份证明。
无参数或不符合前提时输出 `BLOCKED`，退出 3。
无需先在 VM 安装 Q2 软件或改变服务；stdin 方式也无需在 VM 留下脚本文件。

## 一次报告的范围

| 报告组 | 收集的事实和限制 |
| --- | --- |
| 现有 guest | 当前 boot、kernel、namespace 及匹配的 guest 提示 |
| 原始/指定 revision 配置 | 固定配置成员的摘要及内部绑定；不把同目录 SHA 文件当作独立管理授权 |
| 固定程序 | 配置所绑定的解释器、worker、native、systemd-run/systemctl 字节摘要及文件身份；不执行 |
| 源码声明 | detached HEAD 与配置 commit 声明是否相符；不冒充完整源码或干净树校验 |
| 所选旧 slot 与存储 | 当前目录身份、匹配挂载、配置声明的 project/硬限额；不重新查询 quota |
| 所选账户与 query 父级 | 配置所引用的现有 UID 和 query slice 身份/当前事件；不视为 Q2 委派 |
| Q2 尚未交付组 | 安装 wheel、普通 broker/ledger、用户 manager/委派、新分配、独立父级、原预算、容量、空输出目录及原监督入口 |

配置只描述各自选中的 slot，不覆盖所有后续 Q1 实验或历史分配。
旧 slot、曾用预算和 reservation 均不能因此复用为新 Q2 对象。
当前目录和挂载事实不是新的容量预算、历史峰值测量或 Q2 准入证明。
原始 `UNKNOWN`、`INCOMPLETE`、成功的 slot004 及所有保留 payload/证据不变。

`EXPORTED`（退出 0）只表示所选读取组完整；`PARTIAL`（退出 3）保留独立组的具体缺口。
局部失败不要求逐条重跑：返回整个 JSON 后，按同一报告统一定位。
所有结果均保持 Q2/Q3/production acceptance 为 false；不会自动生成 fixture。

## 有限读取与边界

受保护磁盘对象通过目录 fd、逐层 no-follow 和类型/所有者检查读取；不执行来自配置的代码。
成员、文件大小、配置复杂度、总输入及总输出有界；不扫描任意日志或 payload 树。
文件内容读取前后核对身份/大小/修改元数据，导出只是各组的当前观察，不是全机原子快照。
磁盘内容读取使用 no-atime；proc/sysfs 为固定选择。有限字节数和 `O_NONBLOCK` 不能给
阻塞磁盘 I/O 提供硬超时保证，原调用者仍负责独立监督；SSH 超时不等同于远端退出证明。

## 后续批量接续

收到完整私有报告后，一次核对可沿用的既有事实与尚未交付的准确 Q2 对象，准备对应装配材料。
本导出不把尚未提供的 wheel、空 ledger、用户委派或原监督入口虚构为已经存在。
待准确 fixture 已交付，使用 [完整 fixture 前检、原监督和离线复核](E3_QUOTA_Q2_HANDOFF.md)。
独立前检不会产生可复用的原 supervisor 身份；正式执行仍自行准入。

本批还修复完整 fixture 前检的两个现场兼容性问题：

- 接受与已固定源文件及当前解释器相符的正常 Python 缓存，仍拒绝额外/错源/篡改缓存。
  使用有界 no-follow 读取和新编译字节比较，不执行缓存。
- 对普通 resident 的入口、policy、安装内容、程序和声明位置检查普通身份的目录访问前提。
  root 自身能读取不再代替普通账户能读取；ACL 依赖情况保留未证明状态。
  这是保守的 DAC 前提检查，不代替真实账户执行、LSM 或实际宿主验收。
