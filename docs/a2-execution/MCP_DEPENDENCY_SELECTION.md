# E1–E3 MCP 实施选型记录

本记录是准确设计基线 `79f73faedcd9cde4164b0d1625782dae27db6c2f` 在 E1–E3 closure 后的实施事实，
不修改三层文档，不授权 E4 当前客户端接入、E5 GX10/S2 或 E6 真实 NAS。

## 已冻结依赖

2026-09-22 在隔离 Linux x86_64 / Python 3.12 环境安装并检查包内 API，选定：

| 包 | 版本 | 实际用途 | 上游包声明的许可证 |
| --- | --- | --- | --- |
| 官方 `mcp` | 2.2.0 | low-level Server、Streamable HTTP、认证上下文与资源发现 | MIT |
| `PyJWT[crypto]` | 2.14.0 | 成熟 JWT/JWK 解析与签名／claims 验证 | MIT |
| `cryptography` | 50.0.1 | PyJWT 的 RSA／ECDSA 密码实现 | Apache-2.0 OR BSD-3-Clause |

全部传递依赖、下载来源摘要由根目录的
[`requirements-mcp-linux-x86_64-py312.lock`](../../requirements-mcp-linux-x86_64-py312.lock) 冻结。
该文件属于明确平台的安装记录；不能宣称已经验证 Python 3.11、aarch64 或 Windows 的 wheel 可用性。
上游许可证事实不改变本仓库“不新增许可证”的决定。MCP/JWT 依赖只属于可选 extra；基础包导入不需要它们。

## 实际协议选择

- 使用 SDK 2.2.0 的 `Server(on_list_tools=..., on_call_tool=...)` 和 `streamable_http_app()`；
  不照搬旧 SDK decorator API，不自写 MCP transport。
- HTTP stateless、JSON response；每次都认证，执行身份始终来自 broker 的持久 operation/reconcile ID。
  MCP 请求取消或断线不等于业务取消。MCP 入口和本地维护 socket 调用同一个 broker。
- 私有 OAuth 采用预定义 public client + 授权码 + PKCE S256；token endpoint authentication method 为 `none`。
  这是外部 issuer 的客户端注册方式，绝不是资源服务器接受未认证请求。
  本项目不实现授权服务器，也不使用客户端静态共享 secret 代替用户授权。
- 启动前核对 issuer 标准发现位置、准确 issuer／authorization／token／JWKS URL、授权码、S256、
  token endpoint method 和所需 scopes。真实 client ID、redirect URI、主体映射留在私有准入文件中。
- 固定 RS256／ES256 非对称白名单，禁止 unsigned、HMAC 降级、opaque token、token 自带密钥 URL；
  PyJWT 先验证签名与准确 issuer/audience、exp/nbf/iat，再映射服务端固定主体。
  JWKS 请求有有限超时、大小、key 数量、TTL、刷新冷却；失败或过期不使用旧密钥继续放行。
- 鉴权后的原始请求先经严格 UTF-8／重复 key／深度／大小／工具 schema 检查，再进入 SDK JSON parser。
  提交 schema 顶层显式声明 object，满足真实 MCP tools/list 的协议验证。
- 逐工具 OAuth scopes 保存在 `_meta.securitySchemes`，HTTP 401 与工具错误均带规范 challenge。
  SDK 的版本化 MCP schema 会丢弃协议外的 top-level 扩展；因此使用 OpenAI 官方列出的 `_meta` 兼容字段，
  不修改或猴子补丁 SDK。E4 仍必须实测当前客户端读取该字段并触发授权界面。
- 七工具公开 outputSchema；结果有 512 KiB 边界，chunk 不复制进文本内容。
  完整文件仍由宿主已认证回调和有界 writer 组装，structuredContent 不代表文件已保存或交付。
- 首版服务只监听 loopback；真实 Tunnel／TLS gateway、端点路由与当前网页连接留在 E4。

## 本专项验证边界

合成 issuer 使用真实临时 RSA 密钥签发 JWT，执行正负验签、轮换/过期/失败拒绝、PKCE 发现和重新授权测试。
官方 SDK 的真实 ASGI 流程以及独立 `127.0.0.1` 临时 TCP listener 均接受合成签名凭据；
测试 broker 为内存依赖替身，不产生实际 Ledger 或 NAS 副作用。
原始 JSON、跨 token 稳定主体、scope／本地撤销、响应预算、Host/Origin 和回执不明保留均分别测试。
这不能代替真实用户 OAuth 链接、issuer 撤销传播、Work 文件桥接或 GX10 进程隔离验收。

首次专项运行发现 SDK 拒绝缺顶层 object 的提交 schema；修复共享 contract 后复验。
随后增加真实 TCP 与回执不明用例，19 项专项测试通过、0 跳过；完整发布结果以总验收记录为准。
严格 warning 门槛又发现 Starlette 测试客户端使用弃用的 AnyIO 别名；测试宿主改为当前
`httpx2.ASGITransport` 与 `anyio.from_thread.start_blocking_portal`，没有屏蔽 warning 或降级依赖。
初次替换暴露 SDK lifespan 的 task-group 必须由同一任务进入和退出，测试宿主已修正这一所有权；
同 19 项在 `PYTHONWARNINGS=error` 下全部通过。

## 直接依据

- [MCP 官方 Python SDK 认证说明](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/authorization.md)
- [MCP 官方低层 Server API](https://py.sdk.modelcontextprotocol.io/api/mcp/server/lowlevel/server/)
- [PyJWT API](https://pyjwt.readthedocs.io/en/latest/api.html)
- [PyJWT 变更记录](https://pyjwt.readthedocs.io/en/latest/changelog.html)
- [OpenAI MCP 鉴权与预定义客户端](https://developers.openai.com/plugins/build/auth)
- [OpenAI 工具 outputSchema 与 securitySchemes 兼容字段](https://developers.openai.com/plugins/reference)

以上网络文档核对于 2026-09-22；可变链接不是依赖身份，准确安装身份由版本与下载摘要固定。
