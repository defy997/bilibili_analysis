# B站视频评论情感分析系统

一个完整的 B 站视频评论情感分析系统，支持实时监控、情感分析、数据可视化等功能。

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              系统架构图                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐      ┌──────────────┐      ┌────────────────────────┐    │
│   │  Chrome 扩展  │      │ Electron    │      │      Django 后端        │   │
│   │  (监控视频)   │◄────►│  (悬浮窗口)  │◄────►│                         │   │
│   └──────────────┘      └──────────────┘      │  • 爬虫模块 (C++)       │   │
│                                                │  • 情感分析 (Python)   │   │
│                                                │  • API 服务 (Django)   │   │
│                                                │  • 任务队列 (Celery)   │   │
│                                                └────────────────────────┘   │
│                                                           │                  │
│                                                           ▼                  │
│                                                ┌────────────────────────┐   │
│                                                │   Redis (缓存/队列)     │   │
│                                                └────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 技术选型
- **后端**: Django + Django REST Framework + Celery
- **爬虫**: C++ (libcurl + nlohmann/json)
- **分析**: ONNX Runtime + SnowNLP + jieba
- **前端**: Electron + Vue 3 + ECharts
- **缓存**: Redis
- **部署**: Nginx + Supervisor

## ✨ 核心特性

### 🔍 智能监控
- **零手动操作**：在B站观看视频时自动检测视频切换
- **毫秒级响应**：视频变化后1-2秒内更新分析结果
- **多格式支持**：支持各种B站URL格式的视频识别

### 🪟 悬浮窗口
- **类Steam悬浮猫**：优雅的桌面悬浮设计
- **透明背景**：现代化毛玻璃效果
- **可拖拽界面**：随意调整窗口位置
- **始终置顶**：不被其他窗口遮挡

### 📊 情感分析
- **实时图表**：ECharts饼图展示情感分布
- **多维度分析**：正面/中性/负面评论统计
- **智能缓存**：相同视频直接返回缓存结果
- **高准确率**：集成多种情感分析算法

### ⚡ 高性能爬虫
- **C++ 实现**：高效的数据爬取
- **代理池**：自动切换代理IP
- **异步处理**：Celery 任务队列
- **SSE 推送**：实时推送爬取进度

## 🚀 快速开始

### 环境要求
- Python 3.10+
- Node.js 16+
- C++ 编译器 (GCC 9+)
- Chrome 浏览器
- MySQL 8.0+
- Redis 7.0+

### 1. 后端部署 (Django)

```bash
# 进入项目目录
cd bilibili_analysis

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 启动 Redis (Celery 消息队列)
redis-server

# 启动 Celery 任务队列 (4 个 worker 并行处理)
celery -A bilibili_analysis worker -c 4 -l info

# 数据库迁移
python manage.py makemigrations
python manage.py migrate

# 启动 Django 服务
python manage.py runserver 0.0.0.0:8000
```

### 2. C++ 爬虫服务编译

```bash
cd crawler_service
mkdir -p build && cd build
cmake ..
make
./crawler_service
```

### 3. 悬浮窗口部署 (Electron)

```bash
cd electron
npm install
npm start
```

### 4. 浏览器扩展安装

1. 打开 `chrome://extensions/`
2. 开启"开发者模式"
3. 加载 `chrome_extension` 文件夹

### 4. 开始使用

1. 启动Django后端服务
2. 启动Electron悬浮窗口
3. 安装并启用Chrome扩展
4. 访问B站视频页面
5. 享受自动化的情感分析体验！

## 📁 项目结构

```
bilibili_analysis/
├── bilibili_analysis/          # Django 项目主目录
│   ├── settings.py            # Django 设置
│   ├── settings_production.py # 生产环境配置
│   ├── urls.py                # URL 配置
│   └── wsgi.py               # WSGI 配置
├── analysis/                  # Django 应用
│   ├── models.py             # 数据模型
│   ├── views.py              # API 视图
│   ├── serializers.py        # DRF 序列化器
│   ├── tasks.py              # Celery 异步任务
│   ├── crawler.py            # Python 爬虫辅助
│   └── sentiment.py          # 情感分析模块
├── crawler_service/           # C++ 爬虫服务
│   ├── src/                  # 源代码
│   ├── include/              # 头文件
│   ├── third_party/          # 第三方库
│   ├── build/                # 编译产物 ⚠️ 不提交
│   └── CMakeLists.txt        # CMake 配置
├── electron/                  # Electron 悬浮窗口
│   ├── main.js               # 主进程
│   ├── src/
│   │   ├── index.html       # 主界面
│   │   ├── emotional-analysis.html  # 情感分析页
│   │   ├── video-audio-analysis.html # 音视频分析页
│   │   ├── user-profile.html          # 用户画像页
│   │   ├── bilibili-login.html       # 登录页面
│   │   └── js/
│   │       └── shared.js    # 共享 JS
│   └── package.json         # 依赖配置
├── chrome_extension/          # Chrome 扩展
│   ├── manifest.json         # 扩展配置
│   ├── content.js           # 内容脚本
│   ├── background.js        # 后台脚本
│   └── welcome.html         # 欢迎页面
├── models/                    # AI 模型目录
│   └── text_sentiment/       # 文本情感模型
├── requirements.txt           # Python 依赖
├── manage.py                 # Django 管理脚本
├── gunicorn_config.py        # Gunicorn 配置 ⚠️ 不提交
├── nginx.conf                # Nginx 配置 ⚠️ 不提交
├── supervisor.conf           # Supervisor 配置 ⚠️ 不提交
└── deploy_production.sh     # 部署脚本 ⚠️ 不提交
```

### ⚠️ 不提交到仓库的文件
以下文件包含服务器配置信息，已在 `.gitignore` 中排除：
- `deploy_production.sh` - 部署脚本
- `gunicorn_config.py` - Gunicorn 配置
- `nginx.conf` - Nginx 配置
- `supervisor.conf` - Supervisor 配置
- `crawler_service/build/` - C++ 编译产物
- `venv/` - Python 虚拟环境

## 🔧 技术栈

### 后端 (Django)
- **框架**: Django 4.2 + Django REST Framework
- **数据库**: MySQL + Redis 缓存
- **爬虫**: C++ (libcurl) + Python (requests)
- **AI 分析**: ONNX Runtime + SnowNLP + jieba
- **任务队列**: Celery + Redis

### 前端 (Electron)
- **桌面应用**: Electron 25+
- **UI**: 原生 JavaScript + CSS3
- **图表库**: ECharts 5
- **特效**: 毛玻璃效果

### 基础设施
- **Web 服务器**: Nginx
- **进程管理**: Supervisor
- **消息队列**: Redis

## 📡 API接口

### 情感分析接口
```
GET /api/analyze/{bv_id}
```

**响应格式**:
```json
{
  "success": true,
  "data": {
    "video_info": {
      "title": "视频标题",
      "bv_id": "BV1xx411x7x1",
      "author": "UP主",
      "view_count": 12345
    },
    "sentiment_stats": {
      "positive_count": 234,
      "neutral_count": 123,
      "negative_count": 45,
      "total_comments": 402
    },
    "emotion_distribution": [
      {"name": "正面评论", "value": 234, "percentage": 58.2},
      {"name": "中性评论", "value": 123, "percentage": 30.6},
      {"name": "负面评论", "value": 45, "percentage": 11.2}
    ]
  }
}
```

## 🎯 使用场景

1. **内容创作者**: 实时了解观众对视频内容的反馈
2. **数据分析师**: 批量分析热门视频的情感倾向
3. **市场研究**: 监测竞品视频的用户评价
4. **学术研究**: B站内容情感分析的辅助工具

## 🔒 隐私与安全

- **本地处理**: 所有分析在本地完成，不上传用户数据
- **最小权限**: Chrome扩展仅请求必要权限
- **开源透明**: 代码完全开源，可自行审计

## 🚀 性能优化

- **智能缓存**: 视频分析结果缓存，避免重复计算
- **异步处理**: 大量评论时采用异步分析
- **连接复用**: WebSocket长连接，减少网络开销
- **内存管理**: 合理的资源释放和垃圾回收

## 🛠️ 开发与调试

### 开发模式
```bash
# Django开发服务器
python manage.py runserver --settings=settings.dev

# Electron开发模式
npm run dev

# Chrome扩展调试
chrome://extensions/ -> 扩展详情 -> 后台页面
```

### 日志查看
- **Django**: 项目logs目录
- **Electron**: 开发者工具控制台
- **Chrome扩展**: 扩展后台页面控制台

## 📈 扩展计划

- [ ] 支持更多情感分析算法
- [ ] 添加评论关键词提取
- [ ] 实现实时弹幕分析
- [ ] 支持批量视频分析
- [ ] 添加数据导出功能
- [ ] 集成机器学习模型优化

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

1. Fork项目
2. 创建特性分支: `git checkout -b feature/amazing-feature`
3. 提交更改: `git commit -m 'Add amazing feature'`
4. 推送分支: `git push origin feature/amazing-feature`
5. 提交Pull Request

## 📄 许可证

MIT License - 详见LICENSE文件

## 🙏 致谢

感谢所有为这个项目贡献代码和建议的开发者！

---

**体验地址**: [GitHub Repository](https://github.com/your-repo/bilibili-sentiment-analysis)

**问题反馈**: [Issues](https://github.com/your-repo/bilibili-sentiment-analysis/issues)

**文档更新**: 最后更新时间 - 2026年2月
