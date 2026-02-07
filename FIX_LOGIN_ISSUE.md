# 修复登录问题指南

## 🐛 问题症状

登录页面显示：
- ❌ "检查失败: Request failed with status code 500"
- ❌ "No module named 'qrcode'"
- ❌ 点击"返回首页"打开新窗口

## ✅ 解决方案

### 1. 安装缺失的Python模块

在项目根目录运行：

```bash
cd d:\code\python\bilibili_analysis
pip install qrcode[pil] Pillow
```

或者使用国内镜像加速：

```bash
pip install qrcode[pil] Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple
```

或者安装所有依赖：

```bash
pip install -r requirements.txt
```

### 2. 重启Django服务

```bash
python manage.py runserver 118.25.39.91:8000
```

### 3. 重启Electron应用

关闭当前Electron窗口，重新启动。

## 🔧 已修复的代码问题

### 修复1：返回首页功能

**文件**: `electron/src/bilibili-login.html`

**修改前**:
```javascript
const goBack = () => {
    window.location.href = 'index.html';  // ❌ 会打开新窗口
};
```

**修改后**:
```javascript
const goBack = () => {
    const { ipcRenderer } = require('electron');
    ipcRenderer.send('close-bilibili-login-window');  // ✅ 关闭当前窗口
};
```

### 修复2：窗口层级和模态

**文件**: `electron/main.js`

**添加**:
```javascript
// 添加关闭监听器
ipcMain.on('close-bilibili-login-window', () => {
    if (bilibiliLoginWindow && !bilibiliLoginWindow.isDestroyed()) {
        bilibiliLoginWindow.close();
    }
});

// 修改窗口配置
bilibiliLoginWindow = new BrowserWindow({
    parent: mainWindow,  // ✅ 设置父窗口
    modal: true,         // ✅ 模态窗口
    hasShadow: true,     // ✅ 增加阴影
    // ...其他配置
});
```

### 修复3：API URL配置

**文件**: `electron/src/bilibili-login.html`

**添加**:
```javascript
const API_BASE = 'http://118.25.39.91:8000';

// 所有API调用改为完整URL
const res = await axios.get(`${API_BASE}/api/sessdata/check/`);
```

### 修复4：添加依赖到requirements.txt

**文件**: `requirements.txt`

**添加**:
```
qrcode>=7.4.0
Pillow>=10.0.0
```

## 📋 验证步骤

1. ✅ 安装Python依赖后，重启Django
2. ✅ 重启Electron应用
3. ✅ 点击"B站登录"按钮
4. ✅ 应该看到登录窗口在最前面
5. ✅ 二维码正常生成
6. ✅ 点击"返回首页"正常关闭窗口

## 🆘 如果仍有问题

### 检查Django日志

```bash
# 查看Django控制台输出
python manage.py runserver 118.25.39.91:8000
```

### 检查Electron控制台

在Electron窗口按 `F12` 打开开发者工具，查看Console标签。

### 常见错误

1. **端口被占用**:
   - 检查 8000 端口是否被其他程序占用
   - 使用 `netstat -ano | findstr :8000` 查看

2. **防火墙阻止**:
   - 允许Python和Electron通过防火墙

3. **依赖版本冲突**:
   - 使用虚拟环境隔离依赖
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

## 📝 修改文件清单

- ✅ `electron/src/bilibili-login.html` - 修复API调用和返回逻辑
- ✅ `electron/main.js` - 添加关闭监听器和模态窗口配置
- ✅ `requirements.txt` - 添加qrcode和Pillow依赖
