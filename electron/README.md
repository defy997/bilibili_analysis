# B站视频情感分析悬浮窗口

这是一个基于Electron开发的悬浮窗口应用，用于实时显示B站视频评论的情感分析结果。

## 功能特性

- 🪟 **悬浮窗口**：类似输入法的小悬浮窗，始终置顶显示
- 📊 **实时分析**：自动检测B站视频变化并分析评论情感
- 🎨 **美观界面**：使用ECharts展示情感分布饼图
- 🔄 **自动更新**：视频切换时自动获取最新分析结果
- 🌐 **网络通信**：通过WebSocket与Chrome插件通信

## 技术栈

- **Electron**: 桌面应用框架
- **Vue.js**: 前端框架
- **ECharts**: 图表库
- **WebSocket**: 实时通信
- **Axios**: HTTP请求

## 安装依赖

```bash
npm install
```

## 运行应用

```bash
# 开发模式
npm run dev

# 生产模式
npm start
```

## 使用说明

1. **启动Django后端**：确保Django服务器在`http://localhost:8000`运行
2. **启动悬浮窗口**：运行`npm start`启动Electron应用
3. **安装Chrome插件**：安装配套的Chrome扩展程序
4. **观看B站视频**：在B站上切换视频，悬浮窗会自动更新分析结果

## 项目结构

```
electron/
├── main.js              # Electron主进程
├── src/
│   └── index.html       # 悬浮窗口界面
├── package.json         # 项目配置
└── README.md           # 说明文档
```

## 通信协议

### 与Chrome插件通信 (WebSocket)

悬浮窗口作为WebSocket服务器监听3000端口，接收Chrome插件发送的视频变化消息：

```javascript
// Chrome插件发送的消息格式
{
  "type": "VIDEO_CHANGE",
  "bvId": "BV1xx411x7x1"
}
```

### 与Django后端通信 (HTTP)

悬浮窗口通过HTTP请求调用Django API：

```
GET http://localhost:8000/api/analyze/{bv_id}
```

## 窗口特性

- **透明背景**：支持背景模糊效果
- **无边框设计**：现代化的悬浮窗体验
- **可拖拽**：点击标题栏可拖动窗口位置
- **窗口控制**：最小化、关闭按钮
- **始终置顶**：不会被其他窗口覆盖

## 开发调试

开发模式下会自动打开开发者工具，方便调试和样式调整。

## 打包发布

```bash
npm run build
```

## 注意事项

- 确保Django后端服务正常运行
- Chrome插件需要正确配置manifest.json
- 首次运行可能需要一些时间加载依赖
- 网络请求有30秒超时限制

## 故障排除

1. **窗口不显示**：检查Electron是否正常启动
2. **图表不加载**：确认网络连接和Django服务状态
3. **WebSocket连接失败**：检查端口3000是否被占用
4. **视频切换无响应**：确认Chrome插件是否正常工作
