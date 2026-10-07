# K1 最小核心接续实现与验证

最终状态见[准确候选冻结与现场返回](Q2_CORE_MINIMAL_CONTINUATION_FIELD_20261007.md)：
K1 已完成，最终 D `a743af326cdff6e4485b69332e2309130d82a915` 的 CI 3/3 成功；
K2 唯一窗口已消耗，guest journal 序列号检查失败，K3/H01/Q4/H11 未执行。
以下分段保留各阶段当时状态，不作为再次执行的依据。

范围 `LH-Q2-CORE-MINIMAL-CONTINUATION-v1`，准确 A
`5d6cefa602e9146f02887ebfaa4b0cad4e376ff2`，独立 C
`8a4c24cefe4abbab193577b2dff48fc49626cae4`；R、Owner B 见治理记录。
三份 A 文档保持原字节；本实现承接独立 C。

## 已实现差异

维护入口移除全宿主 PID/TID/FD/maps writer 扫描、八个观察点、root/TTY 认证及旧
writer 交接。保留目标 QEMU pidfd/start/argv、五镜像身份、guest 静止、正常关机与旧 VM
退出、正常 qemu-img 锁、独立完整备份、镜像/内容比较、一次原配置启动、ext4/内容/容量核验。
新 manifest/receipt v2 明示可信单管理员前提、host writer 未观察且未证明持续排他。
普通 preflight/v1 交接绑定准确 D/manifest/nonce/host boot/原双钟及累计 CPU、峰值 RSS。

维护固定八原件完整交叉核验后生成有界 journal-transition/v1；host BIND、独立 guest
及返回消费者绑定维护前后 boot。增加准确 05c 第四旧批次、四旧八槽固定顺序、07a 固定
身份和全部累计承诺；新 boot 只接受旧 scope 与 cgroup 缺席。历史 UNKNOWN 不改写。
原 loader、runtime/wheel/harness、sudo/sshd 解析和任务权限保持原样。

## 初始实现提交时的验证及限制

开发树相关核心/journal 回归：2037 passed、35 skipped，29.35s。
随后新增普通交接累计用量/错误输入测试所在协调器组：37 passed，0.09s。
这些结果是隔离测试，不是现场维护或 H01/Q4/H11 通过。
前序开发失败保留在本机 `/mnt/data1/tmp/minimal-*.log`；已修复旧三批夹具、身份推导、
删减时误删的固定输入摘要以及测试夹具错误，没有修改现场以迎合测试。

准确候选的静态私料审查、独立 installed、CI 与发行摘要登记仍待完成。
当前 dispatcher allowlist 保持空；K2/K3 均 NOT_RUN，未消费本次窗口。
旧窗口和所有历史证据继续保留。只在全部 K1 条件通过后开始 K2；失败即停止，
K3 不得自行重试或补采。真实维护成功原件出现前不得发行 K3 真实包。

## 准确初始实现和发行登记依据

准确实现 D1 `f9923f96f9e5720355f550a4769400c7509c62ae`，tree
`71d875ce9b80bfe5a226fe2fdf47797e3f6c8e64`，已发布 main。
独立源码副本相关回归 **2050 passed / 35 skipped / 29.58s**；跳过项为需要 root 的
O_NOATIME 系统 ELF、受保护安装和 cgroup fixture，原原因完整保留。
JUnit SHA-256 `ae136668cf252c8d0374251fee4e76b4db5ce04c5d2525b85e9ee984d1c713bc`。
新 venv 的独立 installed **PASS / 94 checks / 292 commands**，report SHA-256
`b814c150cf16861671c4ec1a20a28a0717f98e22504d01e7ac6f2b33ddd3d8d9`。
首次无 Git 元数据的 archive 构建被来源检查拒绝，随后使用准确 detached worktree 构建；
未降低来源检查。私料审查的沙箱父目录投影拒绝和离线回调接口错误也保留，均未进入窗口。
[准确 D1 CI](https://github.com/kongbu0621/infra-local-hand/actions/runs/37593387957)
三个 job 均成功，包含两平台源码及各自独立安装验证；没有重跑。

原八输入、四旧核心20件/36534 B、sshd诊断4件、capacity诊断4件均由保护读取核对。
没有 VM 探测、SSH、marker 或真实核心包。只读摘要 SHA-256
`d7ec3e1aec0f9ba970dfe264453ddc0f860452e8de8b7e1e243a529e421b5d66`。
静态包859成员、100派生目录、17502358 B；原 runtime、wheel、projection 保持准确固定来源。

随后审查修正了 post 阶段的剩余时间：在既有 phase event 中记录实际 window/change 秒数，
消费者按其重建固定 descriptor/命令摘要，并拒绝超过 pre 的剩余时间。没有刷新双钟或新建事件文件。
新增阶段时间/摘要拒绝与目标镜像命令关系校验，受影响测试 **163 passed / 2.22s**；
BIND 的旧 boot/无关 boot 拒绝及原集成测试 **27 passed / 0.38s**。

登记唯一 dispatcher SHA-256 `ea5d6c0abe2ca49af86e2d0c2088bc7ce9ae723a3803d5a9ddc715c480d2c524`。其 field 字节与 D1 相同；
本次跟进仅涉及 host 原件消费者、维护阶段记录和发行登记/测试/文档，原核心执行代码未变。
此登记不证明 K2/K3 通过：最终候选仍须准确 CI、来源冻结后才可开始唯一窗口。
维护与新核心调用方交接已准备，未运行；真实维护失败则 K3 NOT_RUN。

发行登记与阶段绑定/source admission 定向检查 **237 passed / 7.09s**。
同时移除已无调用者的 terminal 会话选项和跳过工具版本核验选项；现存普通工具路径保持
原行为。最终源码、CI 与窗口结果按后续准确候选另记，不借 D1 CI 冒充。

## Journal 序列号格式修复

基于现场登记 `1706e4a`，在已 CLOSED 的 K1 内离线修复目标设备格式错误，不新增功能、
现场读取、窗口或权限。准确已执行 D 的 CI 37595331543 已独立核对为三 job success；
该结果不覆盖本次源码修复。

确定的实现错误是 `JournalDevice` 把批准序列号加上 LF 后才与 sysfs 原字节比较。
[Linux v6.8 virtio_blk.c 的 serial_show](https://github.com/torvalds/linux/blob/v6.8/drivers/block/virtio_blk.c)
直接返回 ID 字节长度，不追加 LF；同版本
[virtio_blk.h](https://github.com/torvalds/linux/blob/v6.8/include/uapi/linux/virtio_blk.h)
限定 ID 为20字节。[QEMU v8.2.2 的 GET_ID 实现](https://github.com/qemu/qemu/blob/v8.2.2/hw/block/virtio-blk.c)
也只复制最多20字节。三份准确 tag 源码已通过 GitHub Connector 直接读取。
所以正确的无 LF 序列号会被原实现拒绝；现场 actual 未被记录，不能把这一确定代码缺陷
扩张为已复原本次具体字节或证明不存在其它现场问题。

本修复改为完整 ASCII 原字节相等，host/descriptor 上限从128/64统一收紧到20。
不使用 strip、前缀匹配、截断或宽松接受 LF/NUL。失败时复用已取得的同一次128 B有界读取，
在原stderr内白名单记录expected/actual字节数和完整hex；不增加读取，不输出其它异常中的路径。
错误码、失败即停止、目标保护、动作次数、旧原件、旧marker和窗口消费均不变。

原guest完成夹具替换了 `observe_device`，没有经过真实 `JournalDevice`，漏掉了格式错误。
新增测试经过真实构造器，替换的仅是合成 block/sysfs I/O，覆盖1/20字节、无LF、错误值、
截断、LF/CRLF/NUL/空白/非ASCII，以及拒绝后无后续ioctl/size/superblock且关闭FD。
另验证host/descriptor边界和有界失败日志；不连接原guest或读取现场设备。

本次 journal 全组及核心接续定向验证 **324 passed / 2 skipped / 2.84s**，含新构造器36例。
两项SKIP分别为执行环境原生PID/proc argv身份不匹配、缺少合成qcow2/ext4工具；不算现场通过。
`git diff --check` 通过。两个维护源为60320/54936 B，均未超过原98304 B上限。
准确新提交的CI另核实，不能借已执行旧D的绿灯宣称本修复通过CI。

本地下一步只需同步准确修复、复用已有固定输入离线核对journal serial可完整表达（≤20 B），
并核对新源码/交接。**不得执行旧K2 caller**：原marker已存在、K2已消费，K3仍被未完成维护阻断。
任何新现场继续须明确处理现存marker/原件与唯一窗口边界；本修复不删除、改名或重放它们。

## 本地合成验证与准确 CI 状态（2026-10-07）

本地已同步准确修复 `93742af9de38a1cd89eca442a2ce7c4ff2645a0d`。
真实构造器的合成 block/sysfs 边界测试及 guest 完成/失败报告测试合计
**86 passed / 0.42s**，无 SKIP；没有使用现场设备作为测试夹具。
同时复核上节链接的 Linux v6.8 和 QEMU v8.2.2 公开源码，确认序列号格式依据。

[准确修复 CI 37602140697](https://github.com/kongbu0621/infra-local-hand/actions/runs/37602140697)
最终为 **cancelled**。classify-change、Windows 成功；Ubuntu 源码、独立安装包、
Linux 启动检查和证据上传步骤均标为 success，但 Ubuntu job 整体为 cancelled。
公开 check-run `112728861562` 的 failure 注释为
“The job has exceeded the maximum execution time of 15m0s”。
不能将步骤成功汇总为准确候选 CI 3/3 通过；本轮没有重跑 CI 或修改其期限。
该记录只补充公开候选的验证状态，不改变既有窗口消耗或授予新的现场执行权限。
