# 代码同步工具使用说明

## 方案对比

### 方案 1：SCP 脚本（简单，立即可用）
- ✓ 无需安装额外工具
- ✗ 不支持增量同步，每次传输所有文件
- ✗ 速度较慢

**使用方法：**
```powershell
# 推送到服务器
.\sync-push.ps1

# 从服务器拉取
.\sync-pull.ps1
```

### 方案 2：rsync 脚本（推荐，需安装）
- ✓ 增量同步，只传输修改的文件
- ✓ 速度快，支持排除文件
- ✓ 可以删除服务器上多余的文件（--delete）
- ✗ 需要安装 rsync

**安装 rsync（Windows）：**

通过 Cygwin 安装：
1. 下载 Cygwin: https://www.cygwin.com/
2. 安装时选择 `rsync` 包
3. 添加到 PATH: `C:\cygwin64\bin`

或者使用 cwRsync：
1. 下载 cwRsync: https://itefix.net/cwrsync
2. 解压到 `C:\cwRsync`
3. 添加到 PATH: `C:\cwRsync\bin`

**使用方法：**
```bash
# 推送到服务器
bash sync-push-rsync.sh

# 从服务器拉取
bash sync-pull-rsync.sh
```

## 配置

### 1. 修改服务器信息

编辑脚本中的以下变量：
```bash
REMOTE_USER="root"          # 你的 SSH 用户名
REMOTE_HOST="118.25.39.91"  # 服务器 IP
REMOTE_DIR="/root/bilibili_analysis/"  # 服务器项目路径
```

### 2. 配置 SSH 免密登录（可选，推荐）

**生成 SSH 密钥：**
```bash
ssh-keygen -t rsa -b 4096
```

**复制公钥到服务器：**
```bash
ssh-copy-id root@118.25.39.91
```

或手动复制：
```bash
type C:\Users\defying\.ssh\id_rsa.pub | ssh root@118.25.39.91 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

### 3. 自定义排除文件

编辑 `.syncignore` 文件，添加不需要同步的文件和目录。

## 注意事项

1. **首次同步前备份**
   - 建议先手动备份重要文件
   - 使用 `--dry-run` 测试：`rsync -avz --dry-run ...`

2. **删除文件**
   - rsync 脚本使用了 `--delete` 参数
   - 会删除目标目录中源目录没有的文件
   - 如不需要，移除 `--delete` 参数

3. **大文件处理**
   - 模型文件（.onnx, .pkl）默认不同步
   - 如需同步，从 `.syncignore` 中删除相应规则

4. **同步冲突**
   - rsync 是单向覆盖，不会自动合并
   - 双向同步时注意先拉取再推送
   - 或使用 git 作为冲突解决工具

## 故障排查

### SSH 连接失败
```bash
# 测试 SSH 连接
ssh root@118.25.39.91

# 查看详细日志
rsync -avz --progress -e "ssh -vv" ...
```

### 权限问题
```bash
# 给脚本添加执行权限
chmod +x sync-*.sh
```

### 路径问题
- Windows 路径：`/d/code/python/bilibili_analysis/`
- 注意路径末尾的 `/` 很重要（有无影响同步行为）

## 推荐工作流程

1. **开始工作前**：`bash sync-pull-rsync.sh`（拉取服务器最新代码）
2. **本地开发**：正常编写代码
3. **完成后推送**：`bash sync-push-rsync.sh`（推送到服务器）
4. **服务器测试**：SSH 到服务器测试功能

## 其他方案

如果觉得命令行麻烦，可以使用：
- **WinSCP**：图形化 SFTP 客户端，支持自动同步
- **VSCode Remote-SSH**：直接在服务器上开发，无需同步
- **FileZilla**：FTP/SFTP 客户端
