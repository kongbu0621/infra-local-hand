# 部署恢复入口：使用与当前边界

本页对应 [部署恢复重构方案](DEPLOYMENT_RECOVERY_REFACTOR.md)。入口是
`python3 -B -m admin.local_hand_deploy`，源码夹具运行需设置 `PYTHONPATH=tools`。
安装态使用 `PYTHONPATH=<所选安装投影>/tools <所选Python> -B -m admin.local_hand_deploy`；
管理员组件沿既有受 manifest 约束的 source projection 发布，变更入口核对所选源码与实际投影，
不从普通业务 wheel 假定存在管理员权限。下列命令以源码夹具环境简写。
保留 `-B`，或在相关进程中设置 `PYTHONDONTWRITEBYTECODE=1`，避免向所选投影写入额外缓存文件。
它管理节点内的文件、固定 systemd 服务和固定网关容器；不提交、恢复执行或重放业务任务。

## 当前可以执行到哪里

已有维护屏障、完整启动选择和实际运行证明的节点，可以生成只读计划，并沿同一部署记录执行、
恢复、补偿或回退。文件身份使用普通持久文件句柄与文件系统绑定；不支持时明确返回未具备迁移条件。
文件、服务和网关适配器均有有限集合与预算，计划不接受自定义 shell、Python 回调或插件路径。

**旧部署引导 T14 尚不能仅靠此入口完成。** 没有最终维护准入检查的旧管理器或本地 CLI，
不会因为新建 `gate.json` 就受其约束。直接停止旧管理器也可能中断已经受理的准备进程。
当前计划器要求原配置已有共享屏障，并通过原进程的只读协议证明实际加载版本；这个要求会拒绝
未迁移旧入口，不能把拒绝报告成迁移成功。

首次迁移仍需明确的过渡安装或既有授权内的受控停机步骤：列出全部旧准入与启动来源，确证其
不能再派发新工作，保留并闭合原在途责任，再建立原选择和维护记录，验证守卫版入口后开放。
旧任务、原失败与历史回执须保留。网关镜像若没有实际启动守卫和受保护的实例就绪证明，也不能
只凭 Compose 标签加入受支持画像。上述内容是实施缺口，未以 profile 中的布尔值替代现场验证。

## 状态初始化与命令

`init-state` 只创建部署数据库和节点锁，不初始化业务准入，不启动服务，也不生成启动选择。
已有状态应直接读取；损坏或缺失的准入记录不能通过重复初始化改成 `OPEN`。

```bash
umask 077
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state /var/lib/local-hand/deployment --node example-node init-state

PYTHONPATH=tools python3 -B -m admin.local_hand_deploy plan /protected/manifest.json \
  > /protected/plan.json

PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state /var/lib/local-hand/deployment --node example-node apply /protected/plan.json

PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state /var/lib/local-hand/deployment --node example-node status

PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state /var/lib/local-hand/deployment --node example-node resume DEPLOYMENT_OPERATION_ID
```

执行这些管理员命令的身份必须能读取受保护配置、持有节点部署锁，并访问固定本地管理协议。
`plan` 不创建部署目录、监督子进程或业务责任；运行证明使用严格只读的
`deployment_observe`。排空步骤才使用 `deployment_status`，按原退出证明闭合责任。

`resume` 使用原计划和原尝试证据；`rollback OP` 对未提交操作选择补偿方向，对已提交操作生成
唯一绑定的回退后继。重复 `rollback OP` 继续同一后继。修订目标需先生成新计划，再调用
`supersede OP PLAN` 显式交接；这会保留前驱效果、原件和恢复责任。

完成状态分别说明本地决定、准入释放与外部连接观察。`check-public SPEC` 只检查明确指定的公网
端点，不隔离服务，也不把公网暂不可达改写成本地部署失败。遇到等待时读报告中的原操作和缺失证明，
确认旧调用闭合后接续，不能通过重建状态、改请求 ID 或重复业务提交绕过未决结果。

## manifest 与 profile

manifest 固定包含：

| 字段 | 含义 |
| --- | --- |
| `schema` | `local-hand-deployment-manifest/v1` |
| `request_id` / `node_id` | 本次幂等请求与准确节点身份 |
| `source` / `target` | 各自的 `deployment_digest`、完整 `selection`，以及显式服务、网关目标 |
| `files` | `{target, source, mode?, uid?, gid?}`；准确删除用 `{target, remove: true}` |
| `profile` | 固定目录、全部入口守卫、只读证明来源、受管服务/网关、文件与观察预算 |

`selection` 的结构由 `local_hand_jobs.startup` 定义；其 `members` 是实际加载的完整配置文件集合，
`components` 绑定配置摘要、载荷摘要、入口类型和运行要求。源选择必须与当前受保护选择完全一致。
同一个部署摘要不能表示两套配置。准备、首次执行及本地 CLI 必须共用最终屏障。

profile 的 `schema` 为 `local-hand-deployment-profile/v1`。必须有
`startup_descriptor`、`maintenance_directory`、`guarded_components`、`probes` 和
`filesystem_support`。文件系统三项声明 `ordinary_handles`、`fsid`、`reboot_verified`
仅选择已经验证的支持画像；不能把尚未执行的重启验证填成通过。
默认文件上限为 64 个、单文件 4 MiB、准备与恢复总预算 64 MiB；失败暂存件同样占预算。

`probes` 只支持固定 Unix `resident`、`prepared`、`mcp` 协议；观察核对 socket 对端 UID、
实际 PID、进程起始 tick、本次开机和加载摘要。MCP 配置摘要采用其实际输入文件集合、模式及端口，
不套用管理器配置的摘要算法。systemd 画像须给出完整共享 reload 范围及其已加载基线；
网关画像须给出固定 daemon、服务、镜像、原 Compose、外部网络身份和实际守卫证明。

## 最小可运行文件夹具

以下生成器只在新的临时目录内生成两个配置版本、一个明确停止的组件描述，以及独立的 gate。
不接触现役服务、真实任务或系统配置。它用于演示文件计划与持久恢复，不能用来证明 systemd、
网关、主机重启或旧入口迁移验收通过。文件系统支持声明在这个夹具中是固定测试输入；生产画像
必须来自已经完成的实际验证。

```bash
fixture_root=$(PYTHONPATH=tools python3 -B - <<'PY'
import hashlib, os, tempfile
from pathlib import Path
from local_hand_jobs import maintenance, startup
from admin.local_hand_deploy.planner import MANIFEST_SCHEMA, PROFILE_SCHEMA

root = Path(tempfile.mkdtemp(prefix='local-hand-deploy-example-'))
gate_dir = root / 'gate'; gate_dir.mkdir(mode=0o700)
config_path, candidate_path = root / 'manager.json', root / 'candidate.json'
selection_path = root / 'selection.json'
def write(path, value):
    path.write_bytes(startup.canonical(value)); path.chmod(0o600)
def configuration(version):
    return {'installation': {'installed': {'payload_digest': 'c' * 64}},
            'maintenance': {'schema': maintenance.CONFIG_SCHEMA, 'node_id': 'example-node',
                'deployment_digest': version, 'directory': str(gate_dir),
                'startup_descriptor': str(selection_path)}}
def deployment(version, config):
    return {'deployment_digest': version, 'selection': {'schema': startup.SCHEMA,
        'node_id': 'example-node', 'deployment_digest': version, 'decision_id': 'example-original',
        'mode': 'stable', 'owner': None, 'permit': None,
        'members': [{'path': str(config_path), 'sha256': hashlib.sha256(startup.canonical(config)).hexdigest()}],
        'components': {'manager': {'configuration_digest': maintenance.digest(
            {k: v for k, v in config.items() if k != 'maintenance'}),
            'payload_digest': 'c' * 64, 'entry': 'local', 'running': False}}}}
old, new = configuration('a' * 64), configuration('b' * 64)
source, target = deployment('a' * 64, old), deployment('b' * 64, new)
write(config_path, old); write(candidate_path, new); write(selection_path, source['selection'])
maintenance.MaintenanceGate(gate_dir, 'example-node', owner_uid=os.geteuid()).initialize(
    'a' * 64, 'example-original', bootstrap=True)
profile = {'schema': PROFILE_SCHEMA, 'owner_uid': os.geteuid(),
    'startup_descriptor': str(selection_path), 'maintenance_directory': str(gate_dir),
    'filesystem_support': {'ordinary_handles': True, 'fsid': True, 'reboot_verified': True},
    'guarded_components': {'manager': {'configuration': str(config_path), 'entrypoints': ['listener']}},
    'probes': {'manager': {'kind': 'resident', 'socket': str(root / 'unused.sock'), 'peer_uid': os.geteuid()}}}
write(root / 'manifest.json', {'schema': MANIFEST_SCHEMA, 'request_id': 'example-request',
    'node_id': 'example-node', 'source': source, 'target': target, 'profile': profile,
    'files': [{'source': str(candidate_path), 'target': str(config_path)}]})
print(root)
PY
)
umask 077
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state "$fixture_root/state" --node example-node init-state
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy plan "$fixture_root/manifest.json" > "$fixture_root/plan.json"
PYTHONPATH=tools python3 -B -m admin.local_hand_deploy \
  --state "$fixture_root/state" --node example-node apply "$fixture_root/plan.json"
```

报告中的 operation ID 可继续用于 `status`、`resume`、`rollback`；不要另造业务任务来验证恢复。
源码下的 `tests/test_local_hand_deploy_files.py` 与 `tests/test_local_hand_deploy_runtime.py`
还覆盖实际临时文件、子进程中断、持久身份、原缺失恢复、独立替换冲突和已提交回退去重。
