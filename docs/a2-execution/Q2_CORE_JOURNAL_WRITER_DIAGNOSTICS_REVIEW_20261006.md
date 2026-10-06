# Journal writer 诊断保留修复

本次为已关闭 T1/T2 范围内的离线修复，基线 `c5ef5894aab5f11ec7c3094a6ea21c1ecea00450`。
它不恢复已消耗的 T3 窗口，也不证明历史 writer 的具体失败原因或 root payload 已执行。
历史现场仍以 [T3 记录](Q2_CORE_JOURNAL_TERMINAL_AUTH_FIELD_20261006.md) 为准。

## 确定缺陷与修复

- 生成 payload 将源码的 `RuntimeError` 类检查错误换成了 `ValueError`，被扫描器自己的
  `except (OSError, ValueError)` 捕获，覆盖为 `GROWTH_WRITERS_UNKNOWN`。现统一异常基类，
  用生成后的真实函数与源码在同一合成 proc fixture 中比较 maps、visibility、drift、deadline 拒绝。
- payload 保留已知固定错误码及直接/嵌套原因的 errno；父进程严格校验五字段失败报告，保留
  reason/errno。请求按 canonical bytes 比较；errno 仅允许 null 或 0–4095 的整数，拒绝 bool。
  缺失、畸形、重复键、错误绑定与额外字段统一拒绝，不记录私有路径或原始错误文本。
- 父进程先保留有效子失败，再执行原有终端恢复检查；后者失败仍为主原因，同时附带子失败。
  捕获超时时只解析已经收到的完整、有效报告，不追加读取、不将 timeout 改为成功。
- 已读到的有界字节或 EOF 先保留，再执行同一次 deadline 检查；失败输出只计数一次。
  没有增加重试、读取次数、kill/terminate、权限、身份例外或现场窗口。

guest 文件的部分赋值等号空格机械缩减以保留原 65536 B 源码上限；该格式操作前后 AST 相同，
字符串字节未被格式操作改写。`git diff -w` 可单独查看行为变化。

## 本地验证

Python 3.12.14，十二文件定向回归：**428 passed，3 skipped**。新增 29 个隔离诊断测试与
1 个整体 root 拒绝测试。coordinator 合成 fixture 显式设定普通身份，另行确认真实入口在 root
身份下先于源码/现场读取拒绝；生产身份检查未修改。

三个 SKIP 分别为云端 PID 与可见 proc namespace 不匹配、缺少 native qcow2/ext4 工具、无法取得
真实普通身份（errno 1）。它们不是通过，也不能替代普通宿主或现场验收。
源码及生成 payload 的内存编译、`git diff --check` 通过。发布后 CI 须按准确 SHA 独立核对。

| 对象 | 字节 | SHA-256 |
| --- | ---: | --- |
| `q2_journal_growth.py` | 65533 | `9acc17d950f44ddfbdb38d3f1f6b0394a0016889fd155b68dae3ee0e67ce481e` |
| `q2_journal_growth_guest.py` | 65438 | `49e2aefe3e5ff7b702133125d8da7007c05ee0021e64e150ce2d419583614f55` |
| `q2_host_kernel_facts.py` | 15055 | `947469560ca3bdc4997a56739b42561c4a616a5dc8b250b919db589689eecc02` |
| payload（合成 D=`d`×40） | 23848 | `d1561adca28798b100248a2b0e72e3dc26d829166af817c6c79b5d1bd0328ef2` |

没有调用 sudo/writer 现场入口、SSH 或维护动作。扩容仍未执行，H01/Q4/H11 均未执行。
原有安全检查、15s/900s/780s、累计维护次数、历史 UNKNOWN 和暂停支线的约束全部保留。

## 准确发布结果

修复已非强制发布到 `main`，准确提交 `aba18e33f79295f3df1964606e389297d1a8a26a`，
tree `628ec75bd3b34615d4896607942d9cbdd2bb85d4` 与本地已验证树一致。
[CI 37450280680](https://github.com/kongbu0621/infra-local-hand/actions/runs/37450280680)
attempt 1 已完成，结论 `success`，classify-change、Windows、Linux 三个 job 均成功；
源码及独立安装 wheel 验证通过，没有重跑。后续准确 A 为文档提交，没有追加源码改动。
本结果不证明历史现场原因已解决，也不批准另一现场窗口。
