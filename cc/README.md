# Hermes SSH 插件

该插件通过系统自带的 `ssh` 命令执行经过白名单校验的远程诊断或服务操作。它不依赖第三方 Python SSH 库。

## 配置

在主控机上确保 SSH 别名可用，例如 `~/.ssh/config`：

```sshconfig
Host node-1
    HostName 192.168.1.100
    User hermes-ops
    IdentityFile ~/.ssh/id_ed25519_hermes
```

设置插件允许访问的主机：

```bash
export HERMES_SSH_HOSTS="node-1,node-2"
```

空的 `HERMES_SSH_HOSTS` 会拒绝所有请求。

## 运行测试

```bash
echo '{"target_host":"node-1","command":"free -m"}' \
  | python3 hermes_ssh_plugin.py
```

测试拒绝策略：

```bash
echo '{"target_host":"node-1","command":"rm -rf /"}' \
  | python3 hermes_ssh_plugin.py
```

## Hermes 注册

将 `hermes_tool_schema.json` 中的 schema 注册为 `execute_remote_ssh` 工具，并将执行入口配置为：

```text
python3 /absolute/path/to/hermes_ssh_plugin.py
```

插件从标准输入读取一个 JSON 请求，并向标准输出返回一个 JSON 响应。

## 安全注意事项

- 仅在你管理或获授权的服务器上使用。
- 建议使用 SSH 别名和固定密钥，不要把私钥放进 Hermes prompt 或工具参数。
- 插件使用 `StrictHostKeyChecking=accept-new`；生产环境仍建议预先维护 `known_hosts`。
- 如需增加命令，请同时更新脚本中的正则白名单和 schema 描述，并先进行代码审查。
