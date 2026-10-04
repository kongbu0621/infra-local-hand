# Local Hand core acceptance delivery：部分实现与未签发复核

2026-10-04 接续说明：本文保留部分 D 的实现事实。当前输入绑定修订为 OPEN / REVISION REQUIRED，
准确路线见[修订复核登记](../governance/Q2_CORE_BINDING_FINALIZATION_AMENDMENT_BASELINE.md)和
[核心协作交接](Q2_CORE_CLOUD_LOCAL_HANDOFF_20261004.md)。后文旧静态预像准备顺序不构成当前现场执行入口。

## 结论

`LH-Q2-CORE-ACCEPTANCE-DELIVERY-v1` 已按 `R → A → B → C → D` 形成一个
**fail-closed、不可发行的部分 D**。本复核不把该 D 描述为完整实现、冻结 package、现场
readiness 或验收 PASS。

- 实际 field package：**未生成、未冻结**；
- 发行状态：`NOT_ISSUED`；
- O_EXCL marker：`0`；
- carrier request：`0`；
- H01/Q4/H11 run：均为 `0`；
- 真实 Local Hand 任务执行：`NO`；
- 结果和证据收回：`NO`。

当前 release gate 在管理 anchor 重鉴证、对象不存在性检查、host window 取样、marker 和
`Popen` 之前执行。其 dispatcher digest allowlist 为空，dispatcher 自身
`releasable=false`，所以本 D 即使收到格式有效的 package 或补入完整管理预像，也不能消费
一次性授权。

## 固定治理链和候选

| 角色 | 精确值 |
| --- | --- |
| R | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` |
| A | `74366b3fe41e675b1aa2d677228714a5606c275c` / tree `7df4fd0c876df13af4ec73c6f910272a72d7ea4d` |
| Owner B | `LH-Q2-CORE-ACCEPTANCE-DELIVERY-CLOSURE-20261003-01` |
| 独立 bookkeeping-only C | `a8dd077392ebb656770c8f94ca3b051e93fc296d` / tree `b0d651ea5cbc2c408bb43ce6f3cdc5becd5170c6` |
| 部分实现 D | `520f77f578b90d31870517e33e29bee42918f3c0` / tree `bcffbf66209008ff8dd5db312f53af8ced824cff` |
| 固定 core candidate | `4b6e4a7c403362358192086b88679e1326dcb2e1` / tree `4d4349580c9f4b67cc26f601126849c2bc8d76a4` |
| candidate direct parent | `607100a57206f7dc7cfcbd6cae8507cfa599b813` |

D 的唯一 parent 是 C；C 未与实现 squash。固定 candidate、wheel、projection、logical
namespace、预算、case 顺序和一次性规则均未改变。

## D 实际交付

D 新增七个实现模块及七个定向测试模块：

| 文件 | SHA-256 |
| --- | --- |
| `tests/e3_host/q2_core_delivery_bootstrap.py` | `3f1ff0cf3121c0fa463a4797fa1f3de462a3db1b4e7fc71e525128577e2f40bf` |
| `tests/e3_host/q2_core_delivery_contract.py` | `593b8b046f1d1db7ce87afdea7b1e7098d4e69bf243844d202e6c1eccb50de0a` |
| `tests/e3_host/q2_core_delivery_dispatcher.py` | `c2576c748e35d1b4ad8a4cb856a7c7e80b1ee69cf947516271504214a69e8474` |
| `tests/e3_host/q2_core_delivery_entry.py` | `ab14d191fff4f59e7620ecaf484cb1349a242d7ce001674a6c58693c54afef7d` |
| `tests/e3_host/q2_core_delivery_freeze.py` | `46564e2dfb6b56535ec95ec506dea57f44522a0f7279a885133a5ea3612ed5d9` |
| `tests/e3_host/q2_core_delivery_loader.py` | `6cf45d3888e33aa386dacba5411635240c8c8e8585df01844657aedd89fa9c61` |
| `tests/e3_host/q2_core_delivery_package.py` | `ad9d3d000c848f32a4f0e3e015beb943318ffa23073ef04a625250ff8b19c984` |
| `tests/test_e3_q2_core_delivery_bootstrap.py` | `b5cef1622cdc86cc9cc27d4f1157c9f5a5fcdb5e2e1a53c1a686bfd4d9f76c5c` |
| `tests/test_e3_q2_core_delivery_contract.py` | `4817fc8e2d4d4949f88463f188867e8f4164d5c108a6f9fe31e62073ae648828` |
| `tests/test_e3_q2_core_delivery_dispatcher.py` | `ddaf35951e2cccde84fd1b089a537bb1360a771a6328e1d51f63fd63d6bd93f0` |
| `tests/test_e3_q2_core_delivery_entry.py` | `6163b78bc472e8e90ee5151b6e4f1f3185f05f7dad1345b940bf821213edde25` |
| `tests/test_e3_q2_core_delivery_freeze.py` | `7c0dd4dbeae48e184d5810d1a02d11a1dce45265e73a7a6ff9f75f54f9389f01` |
| `tests/test_e3_q2_core_delivery_loader.py` | `5c29c9b3ed1633940b181df1fd34d40796891df89ea863ced0ac04d79e874698` |
| `tests/test_e3_q2_core_delivery_package.py` | `78c5e5959b64a7bb8517fdb21f30835c09f09ddc8a9818a85e0515acc5f0dc30` |

交付内容包括：

1. strict canonical JSON、固定 14 类顶层 record、`.lhfp` builder/parser、loader/bootstrap
   binding 和完整 member inventory 校验；
2. BIND 前后双钟不可刷新映射、guest deadline-aware pipe I/O、真实 stdin EOF、单一输出 frame
   和固定输入/输出上限；
3. held management anchor、本地依赖和固定 argv 重鉴证；同一 held directory fd 贯穿到唯一
   marker/Popen 边界；
4. 非阻塞单次 HELLO → BIND/package → EOF client，以及 create-only capture/final receipt 骨架；
5. candidate/wheel/projection/payload 的 RAM 静态验证、held-dirfd/openat/no-follow/create-only/
   fsync/same-inode reread 原语；
6. H01 → Q4 → H11 的 record/顺序骨架及本地结果收取器；
7. 明确的静态 release gate、当前缺项分类和无现场副作用的 freeze 工具。

超限 carrier output 只读取 `remaining + 1` 的判定字节；超限字节不加入 capture buffer，随即停止。
本地 argv/environment 在 marker 前及 execve 前均以当前 `SC_ARG_MAX` 检查。

## 验证结果

定向命令：

```text
python3 -m pytest -q tests/test_e3_q2_core_delivery_*.py
```

结果为 **62 passed**。七个实现模块通过 `py_compile`，staged diff 通过 `git diff --check`。
定向测试包含 fake effects 和 fake pipes；这些只验证协议拒绝、顺序和预算代码，**不是现场任务、
guest、systemd/cgroup/quota 或结果证据**。

全仓 `python3 -m pytest -q` 也被实际运行，结果为：

```text
3555 passed, 268 failed, 110 skipped, 127 errors in 412.70s
```

该全仓结果不是 PASS，也未被本复核用于发行判断。本 D 没有为追求总绿而修改无关生产代码；
失败和错误没有在本 scope 中被提升、隐藏或转换成成功。

## 静态成员冻结与 package 状态

从无 hooks、无 remote、无 alternates、最小 local Git config 的全新 candidate checkout，针对
精确 D object 运行 freeze 后得到：

| 项 | 结果 |
| --- | --- |
| 状态 | `STATIC_MEMBERS_FROZEN` |
| issuance | `NOT_ISSUED` |
| package | `null` |
| member count | `859` |
| derived directory count | `100` |
| logical member bytes | `17141660` |
| inventory canonical SHA-256 | `73000b592f9a595b63ca7bc369423a911c46bcec58b379430dd11943d8cfdf62` |
| role counts | candidate worktree `845`; Git metadata `9`; field code `3`; wheel `1`; projection `1` |

这只冻结静态成员闭集，不是 `.lhfp`。完整 manifest 还需要已资格化的 management binding 和
private locator relation；因此没有序列化 package，也没有 package basename/bytes/SHA 可以发行。

保留 private archive 的只读复核仍为 zero mismatch，并机械取得 14 项 locator mapping；在未提供
管理完整预像、tokens、argv 和 wrapper bytes 时，它准确返回 `NOT_PREPARED / NOT_ISSUED`。
本地实际 management anchor 的 held-fd 复核通过本地固定文件、key relation、依赖和 cwd 部分，
但以下六组 remote preimage 仍缺失：

- `management_anchor.remote.account_identity`；
- `management_anchor.remote.shell_identity`；
- `management_anchor.remote.sudo_identity`；
- `management_anchor.remote.env_identity`；
- `management_anchor.remote.systemd_run_identity`；
- `management_anchor.remote.python_identity`。

该复核没有连接 guest、创建 marker 或写 package。A 中先前的只读观察区分了真实 QEMU guest 与
当前工具环境；当前工具环境 PID 1 的类型从未被用来判断 guest 是否支持 systemd。本 D 没有用一次
新的远端读取把时点观察伪装成当前 attestation。

## 仍阻止 release 的直接缺项

以下三项是未绑定的 approved input，不是可以从当前 guest 读取后静默采用的新事实：

- `admission.policy_expected_entities`；
- `admission.historical_capacity_obligations`；
- `preparation.retained_paths_and_domains`。

以下八项现场 effect 尚未完成：

- current guest admission collector；
- protected staging、candidate/wheel 安装和 native build；
- existing ordinary account completion；
- H01 normal execution；
- Q4 running-helper cancel subset；
- H11 same-ledger recovery；
- dynamic phase fact extraction；
- complete usage/peak accounting。

此外，在 release 前还必须完成：

1. empty-ledger、admission、gateway/launcher/result/capture/seal 及 H01/Q4/H11 raw bytes 的深层
   schema 和交叉投影；当前 FakeEffects 占位 bytes 可满足局部闭集，不能作为现场真值；
2. dispatcher/remote failure finalization：当前 dispatch/effect 异常只由 bootstrap 以 exit 3 和
   bounded stderr 退出；尚不能在仍可持久化/输出时生成唯一 bounded
   `REMOTE_STOP_AND_RETAIN` final frame；
3. local finalizer 在原 host 双 deadline 内对 capture/fsync/receipt 完成时点的最终检查；当前硬
   release gate 使该路径不可达，但任何 dispatcher digest allowlist 解锁前必须修复并验证；
4. H11 只附着 H11 自己 origin 的原 ledger/request/execution/unit/grant/deadline，且证明不 restart、
   不 reread business result、不新建 unit/grant、不延长 deadline。2026-10-04 勘误：原稿将此处
   错写为 Q4 ledger；原 A 的三个 case 各有自己的 ledger，本次未改变该合同；
5. 完整 D 的独立审计、两次一致 package build/parser、package basename/bytes/SHA 和 release
   digest allowlist；static freeze 还须把当时实际 `SC_ARG_MAX` 结果纳入资格记录；
6. carrier output `remaining + 1` sentinel 的直接超限回归，以及 `SC_ARG_MAX` 失败确实先于
   marker/request 的完整入口顺序回归。原始部分 D 复核时仅有代码审计和局部单元检查；
   2026-10-04 已补齐这两个精确场景，见下节。本项完成不解除其它 release 缺项。

## 2026-10-04：两个既有核心入口回归已补齐

本次只补原 CLOSED A 已要求、且不受 OPEN 输入绑定修订影响的离线测试，未修改 runtime、
schema、预算常量或 dispatcher release allowlist。
`tests/test_e3_q2_core_delivery_entry.py` 新增：

- `test_deliver_once_arg_max_failure_precedes_anchor_marker_and_request`：走真实 `deliver_once`
  入口，测试替身只让入口到达现有参数检查；ARG_MAX 不足时不能进入 anchor 重核、marker、
  request 或 finalizer，目录保持为空，运行源码的 release allowlist 仍为空。
- `test_carrier_remaining_plus_one_is_rejected_without_capturing_overflow`：三个合成 I/O 场景，
  分别覆盖 stderr 剩 7 bytes、剩 0 bytes，以及 stdout 达原上限后的合并总量边界。
  验证超限块不入采集数据、管道关闭、假进程停止及只调用一次 factory。所有原预算常量保持。

指定隔离 venv 的 Python 执行 `-m pytest -q tests/test_e3_q2_core_delivery_entry.py`：
**18 passed in 0.13s**。初次合成 fixture 因缺 USER/LOGNAME 提前触发环境校验，补齐固定合成环境后通过；
没有因此修改运行实现。上述结果只验证入口与有界 I/O，不代表任何真实 H01/Q4/H11、现场
marker/request 或结果收回成功。

## 可执行的后续验收顺序

1. 从既有、可审阅、获准的静态来源提供六组 remote management identity 的完整 preimage；不得
   用当前工具环境推导，也不得为取得它先发第二次或未消费的远端请求。
2. 为三项 unbound approved input 提供精确、逐项可摘要的 retained source relation。若现有 A 无法
   表达这些 bytes/关系，必须先按原 R 形成同一核心 scope 的准确 material amendment；批准文本本身
   不能代替缺失 bytes。
3. 补齐八项 effect、深层验证和 finalizer deadline，保持 production guard；独立审计通过后只把
   精确 dispatcher SHA 加入 release allowlist。
4. 再冻结 private locators 和完整 `.lhfp`，双 build/parse 一致，确认 marker/output absence、预算和
   host deadline 后，才允许创建唯一 marker、发唯一 carrier request。
5. 仅在同一 carrier 内按 `H01_NORMAL → Q4_HELPER_RUNNING_CANCEL_SUBSET →
   H11_SAME_LEDGER_RECOVERY` 执行；任一非 PASS 立即 STOP_AND_RETAIN，不重连、不重试、不发第二
   request。H11 继续使用原 ledger/unit identity 和原 deadline。

namespace/watchdog 仍暂停；production `E3_SUPERVISION_UNVERIFIED` 未修改。本 D 不授权生产启用、
系统配置变更、旧批次重放或把 UNKNOWN/缺证据提升为成功。
