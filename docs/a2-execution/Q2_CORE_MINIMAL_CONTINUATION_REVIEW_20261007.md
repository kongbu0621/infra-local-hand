# K1 最小核心接续实现与验证

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

## 当前验证及限制

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
