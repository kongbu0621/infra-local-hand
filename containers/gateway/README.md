# 固定网关镜像与启动证明

此入口把部署恢复协议中的网关守卫落到实际程序：容器 PID 1 是
`local_hand_mcp.gateway_guard`，它启动固定 nginx 子进程，持有公共 TCP 监听和私有状态 socket。
nginx 只监听容器内 `127.0.0.1`；候选配置只能接受本地核验。稳定选择与管理器维护状态中的
部署摘要、决定 ID 一致后，守卫才开放公共转发。每秒重新取得有界许可；失去许可后关闭监听和
已有转发连接，许可最迟三秒失效。一次公网握手最多一秒，不阻塞本地状态查询三十秒。

这不是通用容器入口或任意命令包装器。当前固定画像是 Linux、私有 PID namespace、容器内
root PID 1、nginx HTTP 反向代理和现有 Docker Engine；TLS 由已选定的外层 HTTPS 入口承担。
不支持 host PID namespace、rootless/user namespace 映射、动态 nginx 模块、TLS 密钥文件、
静态文件服务或任意 nginx 配置目录。

## 构建与选择

先按仓库构建流程生成包含 `gateway_guard.py` 的四包 wheel，并核对其源码身份与实际载荷。
基础镜像须选定官方 **nginx Alpine** 的完整 `sha256` 摘要；Debian 变体不符合此 Dockerfile。
镜像构建独立于部署操作，不会由 `apply` 隐式拉取或构建。

在仓库根目录设置本次 wheel、基础镜像和一个尚不存在的私有输出目录，然后准备上下文：

```bash
python3 tools/admin/build_gateway_image.py \
  --wheel "$GATEWAY_WHEEL" \
  --base-image "$GATEWAY_BASE_IMAGE" \
  --output "$GATEWAY_CONTEXT"
```

默认只写新目录，保存 wheel、Dockerfile 及其摘要，不访问 Docker。
`GATEWAY_BASE_IMAGE` 的形式是 `nginx@sha256:` 后接 64 位摘要。
需要实际构建时，在上述调用中增加 `--build`，并使用另一个尚不存在的输出目录；
可用 `--tag` 指定本地标签，构建后的准确 image ID 写入该目录的 `image-id`。
构建会获取基础镜像及其 Alpine Python 包；不启动容器、创建网络或部署服务。
最终部署画像使用构建得到的准确 image ID，不能使用可变标签。

Dockerfile 显式替换基础镜像的入口，不执行基础镜像的默认启动脚本；安装 wheel 时不联网解析依赖，
不生成字节码缓存。守卫运行时仍核对安装的完整四包载荷摘要。

## 固定配置与挂载

守卫 JSON 严格包含以下九个字段；下面的摘要是格式示意，必须换成本次选择的真实值：

```json
{
  "schema": "local-hand-gateway-startup/v1",
  "node_id": "selected-node",
  "deployment_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "payload_digest": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "manager_socket": "/run/local-hand-manager/manager.sock",
  "nginx_config": "/etc/local-hand-gateway/nginx.conf",
  "public_port": 18080,
  "upstream_port": 18081,
  "status_socket": "/run/local-hand-gateway/status.sock"
}
```

完整启动选择的 `members` 同时包含守卫 JSON 和 nginx 配置。网关组件的
`configuration_digest` 来自 `startup.digest(configuration_binding(config))`；绑定中包含
nginx 配置的逻辑绝对路径、内容摘要、两个端口及状态 socket。不能只绑定守卫 JSON，遗漏实际代理配置。
`payload_digest` 是镜像内四包 wheel 的完整实际载荷摘要。

部署画像中的解析后 Compose 服务必须显式使用：

```json
{
  "entrypoint": ["/opt/local-hand/gateway/bin/python", "-B", "-m", "local_hand_mcp.gateway_guard"],
  "command": ["--config", "/etc/local-hand-gateway/guard.json"],
  "user": "0:0",
  "read_only": false,
  "environment": {},
  "ports": [{"target": 18080, "published": 28081, "host_ip": "127.0.0.1", "protocol": "tcp"}],
  "volumes": [
    {"type": "bind", "source": "/etc/local-hand-gateway", "target": "/etc/local-hand-gateway", "read_only": true},
    {"type": "bind", "source": "/run/local-hand-manager", "target": "/run/local-hand-manager", "read_only": true}
  ]
}
```

此片段须与选定的固定 image ID、container 名称、既有 external network、明确后端容器身份等画像合并。
只发布守卫的 `public_port`；不发布 nginx 内环回端口。外层 HTTPS 入口连接选定的宿主发布端口。
配置和 manager 目录必须同绝对路径只读挂载；manager 使用目录挂载，直接绑定旧 socket 文件会使
管理器重启后继续指向旧 inode。配置文件也必须使用目录挂载，使同目录 rename 的新对象可见；
直接 bind 单个守卫 JSON、nginx 配置文件或 manager socket 均不受支持。
父目录、文件 owner/mode 必须符合受保护启动文件规则。

容器可写层只用于运行目录、PID 和受限临时文件；不要将宿主可写目录交给容器。
nginx worker 降权到基础镜像的 `nginx` 用户，需要保留 `CHOWN`、`SETUID`、`SETGID`；
不能同时配置 `cap_drop: ["ALL"]`。不要用环境变量覆盖解释器、Python 模块路径或入口行为。
共享 manager 必须先完成启动，才能给 MCP/网关候选提供启动许可。

旧未受守卫的部署首次接入时，先按
[受控离线导入](../../docs/DEPLOYMENT_RECOVERY_USAGE.md#旧部署的受控离线导入)核对原入口持久 mask、
原派发锁与在途责任闭合，预装独立名称的新服务定义和独立配置目标；网关必须由准确 Engine
观察为 `absent`。`bootstrap-plan` / `bootstrap-adopt` 只建立全部组件停止的兼容基线，
不会停止业务、删除旧容器、解除旧 mask 或创建新容器。旧配置与记录保留。
成功后沿实际发布的稳定选择生成普通 `plan → apply`，再创建、启动守卫版网关。

## nginx 配置与资源边界

[nginx.conf.example](nginx.conf.example) 是语法示例，其中后端名称和 realm 路径必须替换为已选定值。
它不是现役配置，也不表示这些后端已经创建或鉴权已经验收。
守卫先解析有限语法，再运行固定 nginx 的 `-t`，启动后真实请求默认 `/` 并要求返回 404，
之后才确认本地就绪。

允许唯一 `events`、`http`、`server`，唯一指定内环回监听及固定字面量 location；默认前缀 `/`
必须拒绝。配置文件最多 256 KiB，最多 16384 个 token。拒绝 `include`、额外隐式监听、动态模块、
脚本、证书、静态文件根、任意日志或临时文件路径。stdout/stderr 的容器日志保留策略由所选宿主管理。
配置只描述已有后端的 HTTP/Unix socket 代理，不创建后端、网络或卷。

公共转发至一个固定内环回端口，最多 32 个并发连接，每方向最多 64 KiB 缓冲，空闲时限 60 秒，
单连接总时限一小时；长时间空闲或长流会断开，客户端沿原任务查询/重连，不能因此重提业务。
nginx worker 数固定为 1，worker connections 上限 1024，客户端 body 上限和代理超时也受有限语法约束。
未指定时 nginx 使用其内建 body/timeout 默认值；需要变更时在已选择配置中显式填写受支持值。

## 宿主核验与本轮证据

状态 socket 位于容器内 `/run/local-hand-gateway`，只允许宿主 root 查询。守卫返回它通过 manager
握手取得的宿主 PID/start ticks/boot ID，以及实际配置与载荷摘要、本地就绪和公网就绪状态。
它不自行声明可信 container ID。宿主通过既有 Engine 的准确 container ID/`State.Pid`、私有 PID
namespace、socket `SO_PEERCRED` 及返回的实际进程身份共同核对，再附加 container ID。
容器停止后没有在线 socket，适配器使用已绑定容器的停止状态核对，不强行请求已退出监听。

相关回归入口为 `tests/test_local_hand_mcp_gateway_guard.py`、
`tests/test_local_hand_startup_gateway.py`、`tests/test_local_hand_deploy_gateway_probe.py` 和原适配器测试。
相关回归已通过，包含真实随机 loopback TCP 的双向大报文/半关闭、撤销、过期、并发上限、
空闲超时及真实 Unix 握手；坏状态探针下停止/补偿、Engine/namespace 的边界用例仍是模型测试。
宿主没有可用 nginx 二进制或缓存包，当前执行身份也无法访问 Docker socket，因此本轮没有执行镜像构建、
真实 nginx `-t` 或 Docker 容器生命周期。上述源码、构建入口和真实本地网络证据不冒充这些平台验收。

后续增加显式运行的[隔离 Docker 验收入口](../../tests/e3_host/deployment_recovery_gateway_smoke.py)。
它使用已核对的安装载荷、管理员投影和已构建的准确 image ID，创建随机命名的测试容器；
采用 `NetworkMode=none`，没有宿主端口、外部网络或真实业务挂载。独立的合成管理器使用实际
root Unix 对端身份、维护记录和生产启动授权函数；宿主通过生产观察器核对 Engine PID、
namespace 与 socket 对端。该管理器不是现役业务管理器。

入口检查候选阶段本地可用而公共监听关闭、稳定决定释放后开放、阻断选择发布后撤销访问；
真实执行 create/start/stop/remove 后，故意丢弃已经收到的 Engine 回复，检查沿原尝试观察、
接续及重复调用不再下发。它不声称模拟了 daemon 内部中途崩溃或主机断电。结束时只清理
本次准确绑定的容器；无法确认身份时保留对象并报告失败，不删除其他实例。

以选定安装目录设置 `PYTHONPATH` 后，先做不访问 Docker 的预检：

```bash
python3 -B tests/e3_host/deployment_recovery_gateway_smoke.py --validate-fixture-only
```

在具备本机 root 身份的隔离验收环境中显式运行，输出目录必须尚不存在：

```bash
python3 -B tests/e3_host/deployment_recovery_gateway_smoke.py \
  --run-isolated-gateway --image-id "$GATEWAY_IMAGE_ID" --output "$GATEWAY_CHECK_OUTPUT"
```

当前已通过同一冻结核验包的配置、受保护文件、状态转换和无宿主端口预检；实际镜像构建与
容器执行仍待报告，不计入已通过的平台矩阵。现场版本与最新证据见
[部署恢复实现记录](../../docs/DEPLOYMENT_RECOVERY_IMPLEMENTATION.md#原准备与成果精确安装验证)。
