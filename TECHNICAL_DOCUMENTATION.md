# B站视频评论情感分析系统 - 技术文档

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [技术栈详解](#3-技术栈详解)
4. [核心模块实现](#4-核心模块实现)
5. [数据模型设计](#5-数据模型设计)
6. [API接口文档](#6-api接口文档)
7. [关键技术实现](#7-关键技术实现)
   - [7.1 API请求认证机制](#71-api请求认证机制)
   - [7.2 代理池实现](#72-代理池实现)
   - [7.3 数据清洗流程](#73-数据清洗流程)
   - [7.4 SSE实时推送](#74-sse实时推送)
   - [7.5 WebSocket通信](#75-websocket通信)
   - [7.6 Redis缓存与消息队列](#76-redis缓存与消息队列)
8. [性能优化策略](#8-性能优化策略)
9. [部署方案](#9-部署方案)
10. [使用指南](#10-使用指南)

---

## 1. 项目概述

### 1.1 项目背景

随着弹幕视频平台的蓬勃发展，B站（哔哩哔哩）已成为国内最大的年轻一代视频社区之一。每天产生海量的视频评论和弹幕数据，这些数据蕴含着丰富的用户情感信息。本项目旨在构建一个**智能化的B站视频评论情感分析系统**，实现对视频评论和弹幕的实时监控、自动采集、情感分析以及可视化展示。

### 1.2 项目目标

本系统面向以下用户群体和使用场景：

| 用户群体 | 使用场景 | 核心需求 |
|---------|---------|---------|
| 内容创作者 | 实时了解观众对视频内容的反馈 | 实时分析、快速响应 |
| 数据分析师 | 批量分析热门视频的情感倾向 | 批量处理、多维分析 |
| 市场研究人员 | 监测竞品视频的用户评价 | 竞品对比、趋势追踪 |
| 学术研究者 | B站内容情感分析的辅助工具 | 数据获取、科研支撑 |

### 1.3 核心功能特性

本系统具备以下核心功能：

1. **智能监控**：在B站观看视频时自动检测视频切换，实现零手动操作的自动化分析
2. **毫秒级响应**：视频变化后1-2秒内自动更新分析结果
3. **多格式支持**：支持各种B站URL格式的视频识别
4. **悬浮窗口**：类Steam悬浮窗设计，透明背景、毛玻璃效果、可拖拽、始终置顶
5. **实时图表**：使用ECharts展示情感分布饼图
6. **多维度分析**：正面/中性/负面评论统计，智能缓存避免重复计算
7. **高性能爬虫**：C++实现的爬虫服务，集成代理池、自动切换IP
8. **异步处理**：Celery任务队列，支持大量评论的并行分析
9. **SSE推送**：服务器推送事件，实时展示爬取进度
10. **多模态分析**：支持文本评论、弹幕、音频的多模态情感分析

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              系统架构图                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐      ┌──────────────┐      ┌────────────────────────┐   │
│   │  Chrome 扩展  │      │ Electron    │      │      Django 后端       │   │
│   │  (监控视频)   │◄────►│  (悬浮窗口)  │◄────►│                        │   │
│   └──────────────┘      └──────────────┘      │  • 爬虫模块 (C++)       │   │
│                                                │  • 情感分析 (Python)     │   │
│                                                │  • API 服务 (Django)     │   │
│                                                │  • 任务队列 (Celery)     │   │
│                                                └────────────────────────┘   │
│                                                           │                  │
│                                                           ▼                  │
│                                                ┌────────────────────────┐   │
│                                                │   Redis (缓存/队列)     │   │
│                                                └────────────────────────┘   │
│                                                ┌────────────────────────┐   │
│                                                │   MySQL (数据存储)      │   │
│                                                └────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 组件说明

| 组件 | 技术实现 | 功能描述 |
|-----|---------|---------|
| Chrome扩展 | JavaScript | 监控B站页面视频变化，通过WebSocket通知悬浮窗口 |
| Electron悬浮窗口 | Electron + Vue + ECharts | 桌面端可视化展示，支持多窗口、数据图表 |
| Django后端 | Python Django | REST API服务、业务逻辑处理 |
| C++爬虫 | C++ (libcurl + nlohmann/json) | 高性能数据爬取、代理池管理 |
| 情感分析引擎 | ONNX Runtime + SnowNLP + jieba | 文本/弹幕/音频情感分析 |
| 任务队列 | Celery + Redis | 异步任务处理、分布式计算 |
| 数据存储 | MySQL + Redis | 持久化存储、缓存加速 |

### 2.3 数据流设计

```
用户观看B站视频
       │
       ▼
┌──────────────────┐
│  Chrome扩展检测  │ ◄── URL变化监听 (2秒轮询)
│  视频BV号提取    │
└────────┬─────────┘
         │ WebSocket (ws://localhost:3000)
         ▼
┌──────────────────┐
│  Electron接收    │
│  视频变化通知    │
└────────┬─────────┘
         │ HTTP API调用
         ▼
┌──────────────────┐
│  Django后端      │
│  接收分析请求    │
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐ ┌───────┐
│缓存检查│ │新视频 │
└───┬───┘ └───┬───┘
    │         │
    │    ┌────┴────┐
    │    │         │
    │    ▼         ▼
    │┌────────┐ ┌─────────┐
    ││C++爬虫 │ │Celery   │
    ││数据采集│ │异步分析 │
    │└───┬───┘ └───┬───┘ │
    │    │         │    │
    │    └────┬────┘    │
    │         │         │
    ▼         ▼         ▼
┌─────────────────────────────┐
│     情感分析引擎            │
│  • ONNX文本模型            │
│  • SnowNLP中文模型         │
│  • 音频情感模型            │
└────────────┬───────────────┘
             │
             ▼
┌─────────────────────────────┐
│     结果存储/缓存           │
│  • MySQL持久化             │
│  • Redis缓存               │
└────────────┬───────────────┘
             │
             ▼
┌─────────────────────────────┐
│    Electron多窗口展示       │
│  • 主悬浮窗                │
│  • 情感分析详情页          │
│  • 用户画像页              │
│  • 音频分析页              │
│  • 总体报告页              │
└─────────────────────────────┘
```

### 2.4 系统主要功能概述与性能指标

本系统面向 B 站（哔哩哔哩）视频场景，实现**评论、弹幕、音频**等多源数据的采集、清洗、情感分析与可视化展示，并配套**桌面悬浮窗 + 浏览器扩展**实现“边看边分析”的闭环体验。以下从功能维度与性能维度分别概述。

#### 2.4.1 主要功能模块说明

| 一级模块 | 核心能力 | 典型接口或实现位置 |
|----------|----------|---------------------|
| **视频与情感分析** | 按 BV 号同步/异步分析；评论+弹幕流水线清洗与 BERT 情感推理；结果落库与缓存 | `api/analyze/`、`api/video/async-analyze/`、`api/video/task-status/` |
| **数据爬取** | 视频信息、评论（游标分页/C++ 服务）、弹幕（XML/C++）、音频流 URL；Python Fallback | `analysis/services.py`、C++ `crawler_service` |
| **数据清洗与去重** | Unicode/繁简/Emoji 清理、质量分、白名单、精确/模糊/语义去重 | `DataCleaningPipeline`、`embedding_dedup` |
| **音频与多模态** | 音频下载与分段情感、Timeline 入库；多模态注意力融合与冲突检测 | `analyze_video_audio`、`multimodal_emotion`、`multimodal_attention.py` |
| **异步任务与实时进度** | Celery 并行评论/弹幕/音频任务；Redis 记录进度；SSE 推送 | `analysis/tasks.py`、`crawl_progress_sse` |
| **可视化看板** | 视频综合 Dashboard、用户画像、音频情感曲线、ECharts | `video_dashboard`、`user_profile_dashboard`、`video_audio_dashboard` |
| **用户与认证** | 邮箱验证码注册登录、Session、自定义用户模型 | `api/auth/*` |
| **B 站凭证管理** | 扫码登录、SESSDATA 校验与刷新、WBI 签名、供爬虫使用 Cookie | `api/sessdata/*`、`sessdata_manager.py` |
| **配置与历史** | 全局/用户级过滤与 UI 配置；视频分析历史 | `api/config/`、`api/video/history/` |
| **客户端套件** | Chrome 扩展监控 BV 变化并通过 WebSocket 通知 Electron；Electron 多页面与后端 API 联调 | `chrome_extension/`、`electron/` |

#### 2.4.2 系统性能指标（典型生产配置）

以下指标基于**单机集中式部署**、约 **8GB 内存**、**Gunicorn 1 Master + 3 Workers**、**Celery 3 并发 Worker**、**MySQL + Redis 同机**的典型配置；实际数值随视频评论量、是否启用语义去重模型、并发用户数而波动。

| 性能维度 | 指标说明 | 设计要点 |
|----------|----------|----------|
| **Web 响应** | API 以 JSON 为主；长耗时分析走异步接口，避免阻塞 WSGI Worker | `async_analyze_video` + `task_status` 轮询 |
| **并发模型** | HTTP 请求由 Gunicorn 多进程分担；重任务由 Celery 消费，与 Web 进程隔离 | Redis 作 Broker，避免拖垮 Django |
| **推理吞吐** | 文本情感：BERT+ONNX，默认 mini-batch（如 32）控制单次显存/内存峰值 | `SentimentModel.predict` |
| **爬取能力** | C++ 服务优先承担 HTTP 密集爬取；失败自动回退 Python；评论爬取含随机间隔与重试 | 降低风控与超时概率 |
| **实时性** | 爬取与分析各阶段写入 Redis；前端通过 **SSE** 订阅进度，秒级刷新进度条 | `crawl_progress_sse` |
| **缓存** | Dashboard 等聚合结果可缓存于 Redis，任务完成后失效，减少重复聚合查询 | `dashboard:{bvid}` |
| **资源占用** | 通过控制 Worker 数量、`preload_app`、`max_requests` 周期性回收进程，适配小内存服务器 | `gunicorn_config.py` |

> **说明**：若启用 **sentence-transformers** 语义去重，会显著增加内存占用（约 1～2GB 级），建议在 8GB 机器上按需开启或单独在低峰任务中执行。

#### 2.4.3 系统功能框架结构图

下图采用与业务文档常见的**树形功能分解**形式，概括本系统从用户可见功能到后台支撑模块的层次关系（对应实现以项目代码与 `urls.py` 为准）。

```
B站视频评论情感分析系统（BiliMood）
│
├── 1. 视频与情感分析
│   ├── 同步分析（单视频即时结果）
│   ├── 异步分析（提交任务 + 状态查询）
│   ├── 评论情感分析（清洗 → BERT/ONNX → 三分类）
│   ├── 弹幕情感分析（时间轴对齐）
│   ├── 音频分段情感分析（下载 → 特征 → BiLSTM/ONNX）
│   └── 多模态情感融合（注意力权重 + 冲突检测）
│
├── 2. 数据采集与爬虫
│   ├── 视频元信息（标题、播放量、互动数据等）
│   ├── 评论全量爬取（游标分页 / C++ 服务优先）
│   ├── 弹幕爬取（XML 解析 / C++ 服务优先）
│   ├── 音频流地址解析（Dash / Fallback）
│   └── Python 降级路径（C++ 不可用时）
│
├── 3. 数据清洗与质量控制
│   ├── 文本标准化（Unicode、繁简、URL、Emoji、表情）
│   ├── 垃圾与无意义内容过滤
│   ├── 质量评分与白名单（高赞/高回复直通）
│   └── 多层次去重（MD5 精确 / 编辑距离模糊 / 向量语义）
│
├── 4. 异步任务与实时监控
│   ├── Celery 任务（评论 / 弹幕 / 音频并行或流水线）
│   ├── Redis 任务队列与结果存储
│   ├── 爬取与分析进度写入 Redis
│   └── SSE 实时进度推送至前端
│
├── 5. 可视化与报表
│   ├── 视频综合 Dashboard（情感分布、统计）
│   ├── 用户画像与评论行为分析
│   ├── 音频情感时间线（Timeline）
│   └── ECharts 图表展示（Electron / 浏览器）
│
├── 6. 用户与权限
│   ├── 邮箱验证码注册 / 登录 / 登出
│   ├── 登录态校验（Session）
│   └── 个人过滤与 UI 配置（与全局配置并存）
│
├── 7. B站账号与开放能力
│   ├── 扫码登录与轮询状态
│   ├── SESSDATA 有效性检测与自动刷新
│   ├── WBI 签名与接口合规调用
│   └── 爬虫侧 Cookie 下发
│
├── 8. 配置与历史数据
│   ├── 全局/默认清洗与去重参数
│   ├── 用户视频分析历史与收藏
│   └── 客户端状态上报（可选）
│
└── 9. 客户端套件
    ├── Electron 桌面端（悬浮窗、多页面、本地通知能力）
    └── Chrome 扩展（页面 BV 监控、WebSocket 推送）
```

---

### 2.5 系统功能模块结构与调用关系

#### 2.5.1 模块划分原则

本系统遵循**分层架构（Layered Architecture）+ 面向对象设计**原则，按照"职责单一、信息隐蔽、高内聚低耦合"的标准对整个系统进行模块划分。具体依据如下：

| 划分维度 | 具体标准 | 对应实现 |
|----------|----------|----------|
| **职责边界** | 每个模块只负责一件事，变化原因一致 | `views` 专司 HTTP 入口、`services` 专司业务逻辑、`tasks` 专司异步并发 |
| **复用粒度** | 可独立使用的功能封装为类/模块 | `SentimentModel`（单例）、`DataCleaningPipeline`（流水线） |
| **跨层调用方向** | 上层调用下层，下层不得反向依赖上层 | views → services → models/外设（C++ / ONNX） |
| **并发/同步分离** | 重 I/O 与重计算任务解耦 | Celery `tasks.py` 承载评论/弹幕/音频的异步并行流水线 |
| **外部依赖隔离** | B站 API 调用、C++ 爬虫统一封装，对业务层透明 | `sessdata_manager.py` + `services.py` 中的 C++ Fallback 逻辑 |

#### 2.5.2 系统模块层次结构

系统整体分为 **4 层 9 个模块包**，各包的核心类/函数及其职责如下：

```
B站视频评论情感分析系统
│
├── 表现层（Presentation Layer）
│   ├── bilibili_analysis/urls.py          # URL 路由总表：将 HTTP 路径映射到视图函数
│   ├── analysis/views.py                 # 视图函数集：接收请求、参数校验、调用业务层、返回 JSON
│   └── analysis/auth_views.py             # 认证视图：注册 / 登录 / 登出 / 验证码发送
│
├── 业务逻辑层（Business Logic Layer / Service Layer）
│   ├── analysis/services.py               # 核心服务：爬取 → 清洗 → 情感分析 → 存储全链路
│   │   ├── DataCleaningPipeline            # 数据清洗流水线类（文本标准化 → 过滤 → 去重）
│   │   ├── CrawlerFacade                  # 爬虫外观（C++ 优先 / Python Fallback）
│   │   ├── SentimentInference             # 文本情感推理（调用 ONNX Runtime）
│   │   └── SESSDATA Management            # Cookie 凭证获取与刷新
│   ├── analysis/sessdata_manager.py       # B站凭证管理：
│   │   ├── SessdataManager                 # SESSDATA 生命周期管理（生成二维码 / 轮询 / 刷新）
│   │   └── WbiSigner                       # WBI 签名器（单例，保证密钥线程安全）
│   ├── analysis/analytics.py               # 数据聚合与可视化查询：
│   │   ├── get_comprehensive_dashboard()  # 综合仪表板（评论+弹幕统计，带 Redis 缓存）
│   │   ├── get_user_profile_dashboard()   # 用户画像（等级/VIP/地域分布）
│   │   ├── get_multimodal_emotion_analysis() # 多模态情感融合分析
│   │   └── SSE Progress                    # 爬取/分析实时进度（写入 Redis Hash）
│   └── analysis/multimodal/               # 多模态情感融合子包
│       └── (adaptive_attention_fusion, detect_emotion_conflict)
│
├── 异步任务层（Task Queue Layer）
│   └── analysis/tasks.py                  # Celery 共享任务集：
│       ├── crawl_and_analyze_comments      # 评论爬取+流水线分析（batch 保存）
│       ├── crawl_and_analyze_danmu         # 弹幕爬取+流水线分析（batch 保存）
│       ├── analyze_audio_task              # 音频下载→分段→BiLSTM推理→写入 DB
│       ├── analyze_sentiment_chunk          # ONNX 文本情感推理（Celery Worker 内执行）
│       └── notify_task_complete()          # 任务完成回调（通过 Redis 向 Electron 推送通知）
│
└── 数据持久层（Persistence Layer）
    ├── analysis/models.py                  # Django ORM 模型：Video / Comment / Danmu /
    │                                       # AudioSentiment / MultimodalSentiment / User / UserConfig
    ├── MySQL                               # 关系型数据存储
    └── Redis                               # 缓存（Dashboard）/ 消息队列（Celery Broker）/ SSE 进度
```

> **外部服务（非 Django 项目内）**
> - **C++ crawler_service**：独立运行的 HTTP 服务（默认 `localhost:8081`），承接视频信息、评论、弹幕、音频 URL 的高速爬取，支持 WBI 签名。  
> - **ONNX Runtime 模型**：在 `services.py` / `tasks.py` 中通过 `SentimentModel`（`sentiment_model.py`，单例）加载，运行 BERT 情感分类推理。  
> - **Electron 客户端**：独立桌面进程，通过 HTTP REST API 与 Django 交互，通过 WebSocket 端口 3000/3001 接收 Chrome 扩展通知与 SSE 进度。  
> - **Chrome Extension**：独立浏览器扩展进程，通过 WebSocket 将 BV 号推送至 Electron。

#### 2.5.3 模块调用关系图（包图风格）

下图以 **MVC/分层架构**的视角，展示各模块之间的调用方向与数据流向（箭头表示调用或数据流动方向）：

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          客户端（外部进程）                                    │
│  ┌─────────────┐  ┌───────────────┐  ┌──────────────┐                       │
│  │   浏览器     │  │   Electron    │  │Chrome 扩展   │                       │
│  │ (HTML/ECharts)│ │ (多窗口+通知) │  │(BV 监控)     │                       │
│  └──────┬──────┘  └───────┬───────┘  └──────┬───────┘                       │
└─────────┼──────────────────┼─────────────────┼───────────────────────────────┘
          │ HTTP REST / SSE  │ WebSocket(3000) │ WS 推送 BV
          │                  │                 │
          ▼                  ▼                 │
  ┌─────────────────────────────────────────────────────────┐                 │
  │              bilibili_analysis/urls.py                  │                 │
  │           （URL 路由总表，path → view 映射）            │                 │
  └──────────────────────────┬──────────────────────────────┘                 │
                             │                                                  │
  ┌──────────────────────────▼──────────────────────────────┐                 │
  │           analysis/views.py（视图层 / Controller）       │                 │
  │  • async_analyze_video()  → 调用 services + tasks        │                 │
  │  • video_dashboard()      → 调用 analytics               │                 │
  │  • crawl_progress_sse()  → 读 Redis Hash               │                 │
  │  • get_config()          → 读 models.User               │                 │
  │  • sessdata/* API        → 调用 sessdata_manager        │                 │
  └───────────────┬────────────────────────────────────────┘                 │
                  │                                                         │
     ┌────────────┼───────────────────────────────────┐                     │
     │            │                                   │                     │
     ▼            ▼                                   ▼                     │
  ┌────────────┐ ┌─────────────────────┐  ┌────────────────────────┐        │
  │  services  │ │      tasks.py       │  │    analytics.py        │        │
  │  (业务层)  │ │   (Celery 异步任务)  │  │   (Dashboard 聚合)     │        │
  └─────┬──────┘ └──────────┬──────────┘  └──────────┬─────────────┘        │
        │                  │                        │                       │
        │ ┌───────────────┼────────────────────────┼──────┐               │
        │ │               │                        │      │                │
        ▼ ▼               ▼                        ▼      ▼                │
  ┌────────────────┐ ┌──────────────────────┐  ┌────────────────────┐      │
  │ CrawlerFacade │ │ SentimentModel (单例) │  │ Redis (缓存/SSE/  │      │
  │ C++→Python    │ │  ONNX Runtime BERT   │  │  Celery Broker)    │      │
  └───────┬───────┘ └──────────────────────┘  └─────────┬──────────┘      │
          │           (外接模型文件)                       │                 │
          │                                            │                 │
          ▼                                            │                 │
  ┌─────────────────────┐                            │                 │
  │ C++ crawler_service  │                            │                 │
  │ (独立进程，端口8081) │                            │                 │
  │ WBI签名 + 高速HTTP  │                            │                 │
  └─────────────────────┘                            │                 │
                                                    ▼                 │
  ┌────────────────────────────────────────────────────────┐               │
  │            analysis/models.py（Django ORM）             │               │
  │   Video / Comment / Danmu / AudioSentiment /            │               │
  │   MultimodalSentiment / User / UserConfig              │               │
  └──────────────────────────┬─────────────────────────────┘               │
                             │ MySQL（持久化存储）                          │
                             ▼                                               │
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                        MySQL + Redis                                     │
  │   MySQL: Video/Comment/Danmu/Audio/User 表                              │
  │   Redis: Dashboard 缓存 / Celery Broker / SSE 爬取进度 Hash              │
  └─────────────────────────────────────────────────────────────────────────┘
```

#### 2.5.4 典型调用序列：以异步视频分析为例

以下以"用户提交 BVID → 异步并行分析评论/弹幕/音频 → SSE 推送进度 → 查询完成状态"这一最复杂路径，说明各模块间的调用顺序：

```
浏览器/Electron
  │
  │  POST /api/video/async-analyze/   (bvid=BVxxx)
  ▼
views.async_analyze_video()
  │
  ├─► services.ensure_valid_cookie()            # 获取有效 SESSDATA
  │
  ├─► services.crawl_video_info()               # 爬取视频基本信息（AID/CID/标题）
  │
  ├─► analytics.set_crawl_progress()            # 初始化 Redis 进度 Hash
  │
  ├─► celery.group([                            # 并行提交三个 Celery 任务
  │      crawl_and_analyze_comments.s(bvid,aid,headers,cookie),
  │      crawl_and_analyze_danmu.s(bvid, cid, headers,cookie),
  │      analyze_audio_task.s(bvid, cookie)
  │  ])
  │        │
  │        ├─► tasks.crawl_and_analyze_comments (Celery Worker)
  │        │      ├─► services.crawl_comments()       → C++ 服务（优先）/ Python fallback
  │        │      ├─► DataCleaningPipeline (清洗→过滤)
  │        │      ├─► tasks.analyze_sentiment_chunk()  → SentimentModel.predict()
  │        │      ├─► services.save_comment()          → ORM → MySQL
  │        │      └─► analytics.set_crawl_progress()   → Redis Hash（写入进度）
  │        │
  │        ├─► tasks.crawl_and_analyze_danmu (Celery Worker)
  │        │      └─► (同上，弹幕版)
  │        │
  │        └─► tasks.analyze_audio_task (Celery Worker)
  │               ├─► services.analyze_video_audio()
  │               │      ├─► services.download_audio()
  │               │      ├─► AudioSentimentModel.analyze_segments()
  │               │      └─► ORM bulk_create() → MySQL AudioSentiment
  │               └─► analytics.set_crawl_progress() → Redis Hash
  │
  │  return {"status": "processing", "tasks": {各task_id}}
  ▼
views.crawl_progress_sse() (GET /api/video/crawl-progress/<bvid>/)
  │  ← SSE 流，每秒读取一次 Redis Hash → 推送至前端
  ▼
Electron/浏览器（实时进度条更新）
  │
  │  GET /api/video/task-status/?task_ids=id1,id2,...
  ▼
views.task_status()
  └─► tasks.get_task_results_async(task_ids)
        └─► celery.AsyncResult.get() → 返回各任务结果
  │
  │  return {"tasks": {各task状态}, "summary": {情感统计}}
  ▼
浏览器/Electron
  │
  │  GET /api/video/dashboard/<bvid>/
  ▼
views.video_dashboard()
  └─► analytics.get_comprehensive_dashboard()
         ├─► 读 MySQL（Video/Comment/Danmu，预加载 only() 字段）
         ├─► Redis 缓存（cache_key="dashboard:{bvid}"）
         └─► 返回完整 Dashboard JSON
```

#### 2.5.5 关键设计决策汇总

| 决策点 | 选择方案 | 原因 |
|--------|----------|------|
| **并发模型** | Celery Worker 3 个并发进程 + Gunicorn 3 Workers | 分离 CPU 密集（ONNX 推理）与 I/O 密集（HTTP）工作，避免相互阻塞 |
| **爬虫策略** | C++ 服务优先（端口 8081），Python 静默降级 | 兼顾高并发吞吐（C++）与快速迭代（Python） |
| **情感模型** | ONNX Runtime 推理（BERT，单例） | 避免每次请求重复加载模型；ONNX 与训练框架解耦 |
| **缓存策略** | Redis 缓存 Dashboard（5 分钟 TTL） + SSE 进度（Hash） | 减少 MySQL 聚合查询压力；SSE 进度实时推送 |
| **多模态融合** | 自适应注意力机制（`adaptive_attention_fusion`） | 根据视频类型动态分配音频/文本/弹幕权重，结果存入 `MultimodalSentiment` 表 |
| **认证方案** | Django Session + B站扫码登录（`SessdataManager`） | Session 管理用户状态，SESSDATA 管理 B站 API 凭证，分工明确 |

---

## 3. 技术栈详解

### 3.1 后端技术栈

| 技术 | 版本 | 用途 |
|-----|-----|-----|
| Django | 5.1 | Web框架 |
| Django REST Framework | - | REST API开发 |
| Celery | 5.3+ | 异步任务队列 |
| Redis | 7.0+ | 消息队列、缓存 |
| MySQL | 8.0+ | 关系型数据库 |
| ONNX Runtime | 1.16+ | 神经网络推理 |
| transformers | 4.30+ | BERT分词器 |
| SnowNLP | - | 中文情感分析 |
| jieba | - | 中文分词 |
| requests | 2.31+ | HTTP请求 |
| C++ (libcurl) | - | 高性能爬虫 |
| gunicorn | 21.0+ | WSGI服务器 |

#### 3.1.1 技术架构

本系统采用 **B/S + C/S 双架构并行**的混合部署模式，以 Linux 服务器作为统一的运行平台，Web 浏览器与 Electron 桌面端作为客户端，各自承担不同的用户交互职责。这种设计兼顾了跨平台可访问性（浏览器端）与本地沉浸式体验（桌面端），同时通过统一的后端服务保证数据一致性。

**平台选型与原因**

| 平台 | 技术选型 | 选用原因 |
|------|----------|----------|
| **运行平台（服务端）** | Linux（CentOS/Rocky） | 稳定、安全、低成本；可对接本地 C++ 爬虫服务；Supervisor/Nginx 生态成熟；MySQL/Redis 原生支持 |
| **Web 客户端** | 原生 HTML5 + CSS3 + JavaScript + ECharts | 无需安装、跨平台访问；ECharts 提供丰富图表，支持情感分布饼图、情感波动折线图等；对接 Django REST API |
| **桌面客户端** | Electron（Chromium + Node.js） | 原生桌面体验（悬浮窗、托盘图标、系统通知）；可调用系统 API（音频录制、本地文件）；复用 Web 技术栈降低开发成本 |
| **Chrome 扩展** | Chrome Extension（Manifest V3） | 运行在 B站站内，零手动操作即可感知视频切换；通过 WebSocket 将 BVID 推送至 Electron；权限可控，不干扰用户正常浏览 |

**关键技术框架说明**

以下按层次说明各框架的职责与选型理由：

```
┌─────────────────────────────────────────────────────┐
│                    客户端层                           │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  Chrome 扩展   │  │ Electron     │  │  浏览器   │ │
│  │  (内容脚本)    │  │ 桌面端       │  │ (HTML5)  │ │
│  └──────┬───────┘  └──────┬───────┘  └───┬─────┘ │
│         │ WebSocket       │ HTTP/REST     │ HTTP  │
├─────────┼────────────────┼───────────────┼───────┤
│         ▼                ▼               ▼        │
│  ┌─────────────────────────────────────────────┐  │
│  │          Nginx 反向代理 / 静态资源服务        │  │
│  └──────────────────────┬──────────────────────┘  │
│                         │ HTTP (8000)              │
│  ┌──────────────────────▼──────────────────────┐  │
│  │          Django + Gunicorn (1M+3W)           │  │
│  │  • REST API  • 爬虫调度  • 情感分析编排       │  │
│  └──────────────────────┬──────────────────────┘  │
│                         │                          │
│         ┌───────────────┼───────────────┐        │
│         ▼               ▼               ▼        │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │ Celery     │  │  MySQL     │  │   Redis    │  │
│  │ Worker(3)  │  │ (MariaDB)  │  │  队列/缓存  │  │
│  └─────┬──────┘  └────────────┘  └────────────┘  │
│        │                                       │
│  ┌─────▼────────────┐                         │
│  │  C++ 爬虫服务       │                         │
│  │  (本机 TCP :8081)  │                         │
│  └───────────────────┘                         │
└─────────────────────────────────────────────────┘
```

**1. Django（Web 框架）**

Django 承担系统核心的业务编排层，原因如下：① ORM 屏蔽了 MySQL/MariaDB 的 SQL 方言差异，开发效率高；② MTV 架构将数据模型（models.py）、业务逻辑（views.py）、URL 路由（urls.py）分离，便于维护；③ 内置用户认证系统（AbstractUser），为 B站 Cookie 绑定与多用户管理提供了天然的扩展基础；④ 生态丰富，可无缝集成 Celery（django-celery-results）、Redis（django-redis）等组件。版本选用 Django 5.x，支持 Python 3.10+ 的异步能力。

**2. Gunicorn（WSGI 服务器）**

Django 自带的开发服务器不适合生产环境，Gunicorn 作为 Python WSGI 标准实现，提供了稳定的多进程 HTTP 服务能力。选型理由：① 与 Django 原生兼容，只需 `gunicorn --bind 0.0.0.0:8000 wsgi:application` 即可启动；② 支持 `preload_app` 预加载，减少多 worker 内存占用；③ 支持 `max_requests` + `max_requests_jitter` 自动重启 worker 防止内存泄漏；④ 可通过 `gunicorn_config.py` 灵活配置 workers 数量、线程数、超时等参数，适应 8GB 小内存服务器。生产配置为 1 master + 3 sync workers + 每 worker 4 threads。

**3. Celery + Redis（异步任务队列）**

评论与弹幕的爬取、清洗、情感分析涉及大量 I/O 和 CPU 操作，同步执行会阻塞 Web 请求。Celery 是 Django 生态中最成熟的异步任务框架，原因：① 与 Django 配置无缝集成（`app.config_from_object('django.conf:settings')`）；② 支持 `group()` 并行任务（评论与弹幕同时分析）和 `chain()` 流水线任务；③ Redis 既做消息代理（Broker）又做结果存储（Backend），无需额外部署 RabbitMQ；④ 任务可设置重试（`autoretry_for`）、超时（`time_limit`）、优先级等生产级特性。当前配置 3 个并发 Worker，`apply_async()` 提交任务，`AsyncResult` 查询状态。

**4. MySQL / MariaDB（关系型数据库）**

业务数据（用户、视频、评论、弹幕、情感分析结果）适合用关系型数据库存储，原因：① Django ORM 原生支持，模型变更通过 Migration 管理；② 支持复杂查询（按时间段聚合、按情感标签筛选、按用户维度统计等）；③ MySQL 的 InnoDB 引擎提供行级锁和事务保障，评论并发写入时不会冲突；④ MariaDB 10.x 与 MySQL 8.x 完全兼容，性能相近且在 Linux 发行版中更易获取。

**5. C++ 爬虫服务（高性能爬取）**

数据爬取是系统的性能瓶颈之一。Python `requests` 库在高频 HTTP 请求场景下存在 GIL 限制和解释器开销。C++ 爬虫服务基于 `httplib` 单头文件库和 `nlohmann/json` 实现，原因：① 编译为原生二进制，无 GIL 限制，可轻松支撑数百并发连接；② 与 Django 解耦为 TCP 服务（默认端口 8081），Django 通过 `requests.post` 调用，C++ 故障不影响 Django 主服务；③ 内置代理池管理（GET/POST proxy 接口）、Cookie 管理、反风控重试逻辑；④ Python 层保留完整的 Fallback 实现，C++ 服务不可用时自动降级，确保系统高可用。

**6. ONNX Runtime（神经网络推理引擎）**

情感分析模型（BERT 多语言文本模型、BiLSTM 音频模型）以 ONNX 格式部署，而非 PyTorch 原生推理。原因：① **跨平台**：ONNX 模型可在 Windows、Linux、ARM 等任意平台运行，无需安装 PyTorch；② **推理性能**：ONNX Runtime 提供图优化（常量折叠、算子融合）、内存优化和硬件加速（AVX2/AVX512），推理延迟比 PyTorch 低 30%~50%；③ **内存占用**：ONNX Runtime 的内存分配策略更精细，配合 mini-batch 处理（batch_size=32）可在 8GB 内存服务器上稳定运行；④ **轻量化部署**：Django Worker 无需加载 PyTorch 依赖，镜像体积大幅缩小。

**7. Electron（桌面客户端框架）**

Electron 基于 Chromium + Node.js 构建桌面应用，选型理由：① **技术栈复用**：前端代码（HTML/CSS/JS/ECharts）与 Web 端共享，无需额外学习成本；② **系统能力**：可访问本地文件系统（保存分析报告）、调用系统通知 API（任务完成提醒）、创建托盘图标（常驻后台）；③ **跨平台**：一次开发可打包为 Windows exe 和 Linux AppImage；④ **WebSocket 服务**：Electron 内置 Node.js，可直接运行 WebSocket Server，接收 Chrome 扩展的 BVID 推送。

### 3.1.2 关键功能/算法设计

本节选取系统中 6 项核心技术功能，详细说明其算法流程、关键设计决策与优化技巧。

---

#### 3.1.2.1 数据清洗流水线（DataCleaningPipeline）

**功能定位**：将爬取的原始评论/弹幕文本，经过清洗 → 过滤 → 去重三阶段处理后，输出高质量分析语料。

**流程图**

```
原始评论列表
    │
    ▼
┌─────────────────────┐
│  阶段一：文本标准化  │   normalize_unicode()     — 全角→半角
│                     │   convert_traditional...()  — 繁体→简体（OpenCC）
│                     │   remove_emoji()           — Emoji + B站表情过滤
│                     │   compress_repeated_chars() — 重复字符压缩（最多3次）
└──────────┬──────────┘
           │ 清洗后文本列表
           ▼
┌─────────────────────┐
│  阶段二：质量过滤    │   filter_by_length()       — 长度上下限过滤
│                     │   is_spam_content()        — 垃圾检测（纯数字/符号/单字符重复）
│                     │   get_chinese_ratio()       — 中文占比不足过滤
│                     │   is_meaningful_text()      — 综合判断（含白名单机制）
└──────────┬──────────┘
           │ 通过过滤的文本
           ▼
┌─────────────────────┐
│  阶段三：多层次去重  │   exact_dedup()            — MD5 精确哈希去重
│                     │   fuzzy_dedup()             — 编辑距离模糊去重（difflib）
│                     │   embedding_dedup()          — 向量语义去重（sentence-transformers）
└──────────┬──────────┘
           │ 最终语料
           ▼
   情感分析引擎
```

**关键设计决策**

| 决策点 | 实现方式 | 原因 |
|--------|----------|------|
| **白名单机制** | 高赞（like≥50）或高回复（reply≥10）评论跳过过滤 | 避免高质量评论因文本短小/含英文被误杀 |
| **多层次去重顺序** | 精确哈希 → 模糊编辑距离 → 语义向量 | 从快到准逐步过滤，减少昂贵语义计算的候选量 |
| **配置来源** | 所有阈值从 `UserConfig` 表读取，支持用户级覆盖 | 兼顾默认值与个性化调参需求 |
| **内存优化** | 去重过程保留元数据（点赞数）用于质量选择 | 同组重复内容中保留点赞最高的 |

---

#### 3.1.2.2 文本情感分析推理（SentimentModel）

**功能定位**：将清洗后的中文文本批量推理为 0～1 情感得分（正面概率），结果分为 positive（≥0.6）、neutral（0.4～0.6）、negative（≤0.4）。

**推理流程**

```
输入文本列表 [str, str, ...]
    │
    │  mini-batch 分组（默认 batch_size=32）
    ▼
┌──────────────────────────────────────────────────┐
│           BERT Tokenizer（transformers）          │
│  • padding / truncation / max_length=128         │
│  • return_tensors="np"（NumPy，无需 PyTorch）    │
└──────────────────────┬───────────────────────────┘
                       │ {input_ids, attention_mask, token_type_ids}
                       ▼
┌──────────────────────────────────────────────────┐
│        ONNX Runtime InferenceSession              │
│  • GraphOptimizationLevel = ORT_ENABLE_ALL        │
│  • 单例模式：Worker 进程启动时加载一次            │
└──────────────────────┬───────────────────────────┘
                       │ logits [batch, seq_len, 2]
                       ▼
┌──────────────────────────────────────────────────┐
│              Softmax → 取 label=1 概率            │
│  score = exp(logit₁)/Σexp(logitⱼ)               │
│  返回各文本的正面情感概率 (0~1)                   │
└──────────────────────────────────────────────────┘
    │
    ▼
  get_sentiment_label(score)
  ├── score ≥ 0.6 → "positive"
  ├── score ≤ 0.4 → "negative"
  └── else       → "neutral"
```

**关键设计决策**

| 决策点 | 实现方式 | 效果 |
|--------|----------|------|
| **模型格式** | ONNX 而非 PyTorch 原生 | 推理延迟降低 30%～50%；Django Worker 无需 PyTorch 依赖 |
| **推理粒度** | mini-batch（32 条/批） | 控制单次内存峰值，避免 8GB 服务器 OOM |
| **加载策略** | 单例模式（`__new__` 覆写） | 多 Worker 进程各加载一次，不重复占用内存 |
| **输入兼容** | `token_type_ids` 缺失时自动补零 | 兼容不同 BERT 分词器变体 |

---

#### 3.1.2.3 音频情感分析（AudioSentimentModel）

**功能定位**：将 B站视频音频流下载后，分段提取 MFCC/Mel-Spectrogram 等特征，通过 BiLSTM-ONNX 模型推理各时间段的情感类别（angry/happy/neutral/sad/fearful/surprise），再映射为 0～1 极性分数。

**分段分析流程**

```
音频流 URL
    │
    ▼
ffmpeg 下载 & 转换 → wav（16kHz，单声道）
    │
    │  sliding window（segment=15s, overlap=5s）
    ▼
┌────────────────────────────────────────┐
│        特征提取（librosa，768维）       │
│  • MFCC（13维）×3（均值/标准差/ΔΔ）   │
│  • Mel-Spectrogram 统计量             │
│  • 频谱质心/带宽/滚降点                │
│  • 色度特征 / 过零率 / RMS 能量        │
│  • 音高统计（piptrack）               │
└────────────┬───────────────────────────┘
             │ 特征向量 [768]
             ▼
┌────────────────────────────────────────┐
│     BiLSTM-ONNX 推理（单例）           │
│  • 6 类 Softmax 输出                   │
│  • 情感极性映射（EMOTION_POLARITY）    │
└────────────┬───────────────────────────┘
             │ (label, probabilities[])
             ▼
┌────────────────────────────────────────┐
│        极性映射 → 0~1 分数              │
│  polarity = Σ P(emotion) × polarity()  │
│  例：happy=0.7×0.85 + sad=0.2×0.20     │
└────────────┬───────────────────────────┘
             │ [{time_offset, score, label, probs}]
             ▼
        MySQL AudioSentiment 表（bulk_create）
```

**关键设计决策**

| 决策点 | 实现方式 | 效果 |
|--------|----------|------|
| **特征维度固定** | 不足 768 维补零，超过截断 | 适配固定输入维度的 ONNX 模型 |
| **重叠分段** | segment=15s, overlap=5s | 平滑情感过渡曲线，避免分段边缘信息丢失 |
| **尾段处理** | 短视频（<30s）自动缩小窗口；尾段<5s 丢弃 | 防止过短音频段干扰分析 |
| **内存回收** | 每段处理后 `del` 中间变量 + `gc.collect()` | 在 8GB 机器上处理长音频（>10分钟）不崩溃 |
| **情感极性映射** | 手工定义 6 类 → {0.15~0.85} 映射表 | 比直接取 max(probs) 更符合情感连续认知 |

---

#### 3.1.2.4 多模态情感融合（adaptive_attention_fusion）

**功能定位**：融合文本评论、弹幕、音频三路情感信号，输出整体情感判断与注意力权重，并检测模态间冲突。

**算法流程**

```
各模态独立情感分布
  text = {pos, neu, neg}   ← from Comment 表统计
  danmu = {pos, neu, neg}  ← from Danmu 表统计
  audio = {pos, neu, neg}  ← from AudioSentiment 表统计
    │
    ▼
┌─────────────────────────────────────────────────────┐
│        Step 1: 根据视频类型确定基础权重              │
│  type_weights = {                                   │
│    'music':    {audio:0.6, text:0.2, danmu:0.2},   │
│    'tutorial': {audio:0.2, text:0.5, danmu:0.3},   │
│    'vlog':     {audio:0.4, text:0.4, danmu:0.2},   │
│    'game':     {audio:0.3, text:0.3, danmu:0.4},   │
│    'general':  {audio:0.35,text:0.35,danmu:0.3}    │
│  }                                                   │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Step 2: 基于情感强度动态加权                         │
│  strength(emotion) = max(vals) - min(vals)          │
│  strength_bonus = strength × 0.1                     │
│  adjusted_w = (base_w + bonus) / Σ(base_w + bonus) │
└──────────────────────┬──────────────────────────────┘
                       │ adjusted_weights {audio, text, danmu}
                       ▼
┌─────────────────────────────────────────────────────┐
│  Step 3: 加权融合                                    │
│  fused[emotion] = Σ adjusted_w[mod] × mod[emotion] │
│  例：fused_pos = 0.35×0.7 + 0.35×0.6 + 0.3×0.5   │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    融合情感分布    注意力权重    主导情感
    {pos,neu,neg}  {audio:text:danmu}  max(fused)
         │             │
         ▼             ▼
┌─────────────────────────────────────────────────────┐
│  Step 4: 冲突检测（detect_emotion_conflict）        │
│  对每对模态：若主导情感不同且置信度>阈值（0.4）      │
│  则标记冲突类型（audio-text / text-danmu）           │
│  并计算 severity = |conf₁ - conf₂|                 │
└─────────────────────────────────────────────────────┘
    │
    ▼
 最终输出 {fused_emotion, attention_weights, dominant_emotion, conflict_info}
```

---

#### 3.1.2.5 异步并行流水线（Celery Tasks）

**功能定位**：以 BVID 为单位，并行执行评论爬取分析、弹幕爬取分析、音频分析三个独立任务，利用 Celery Group 实现真正的并行吞吐。

**流水线设计（以评论任务为例）**

```
Celery Group([
  crawl_and_analyze_comments.s(bvid, aid, headers, cookie),
  crawl_and_analyze_danmu.s(bvid, cid, headers, cookie),
  analyze_audio_task.s(bvid, cookie)
])
    │
    ├──► Task 1: crawl_and_analyze_comments
    │         │
    │         ├─ crawl_comments() → C++(优先) / Python(降级)
    │         │
    │         ├─ batch_size=32 流水线
    │         │    循环:
    │         │      ① 逐条 clean_text()
    │         │      ② is_meaningful_text() 过滤
    │         │      ③ 凑满32条 → analyze_sentiment_chunk()
    │         │         └─ SentimentModel.predict(32条)
    │         │      ④ 逐条 save_comment() → MySQL
    │         │      ⑤ 每100条 → set_crawl_progress() → Redis
    │         │
    │         └─ 返回 {type, count, pos/neu/neg, elapsed}
    │
    ├──► Task 2: crawl_and_analyze_danmu
    │         └─ 同上，弹幕版（batch_size=64，更宽松）
    │
    └──► Task 3: analyze_audio_task
              └─ services.analyze_video_audio()
                   → download_audio() → analyze_segments()
                   → bulk_create(AudioSentiment)

每任务完成后:
  ├─► analytics.set_crawl_progress() → Redis Hash
  ├─► _update_overall_progress()     → 检查3任务完成状态
  └─► notify_task_complete()          → Electron 通知
```

**关键设计决策**

| 决策点 | 实现方式 | 效果 |
|--------|----------|------|
| **流水线 vs 批量** | 边爬边分析（pipeline）而非全量爬完再处理 | 评论量大时减少内存峰值；实时感知爬取进度 |
| **进度写入** | 每 100 条评论写一次 Redis Hash | SSE 前端每秒轮询可感知最新进度 |
| **Celery 可用性检测** | `redis.Redis.ping()` 失败则同步回退 | Redis/Celery 故障时系统不宕机，保证可用性 |
| **子线程关闭连接** | Celery 任务子线程中 `connection.close()` | 防止 Django 子线程泄漏 MySQL 连接 |

---

#### 3.1.2.6 爬虫外观模式（C++ 优先 + Python 降级）

**功能定位**：为所有外部 HTTP 爬取操作提供统一入口，C++ 服务优先承担高频爬取，Python 实现作为兜底，两路逻辑对上层业务代码完全透明。

**调用决策流程**

```
services.py 中任一爬取函数被调用
  例: crawl_comments(aid, headers)
          │
          ▼
  requests.post("http://localhost:8081/crawl/comments",
                json={aid, cookie}, timeout=300)
          │
     是否成功响应？
    ┌────┴────┐
    │ 是      │ 否（连接超时/服务不存在）
    ▼         ▼
  data.get('success')  调用 Python 实现
  为 true?             例: _crawl_comments_python(aid, headers)
    │                        • 游标分页
    │                        • 随机间隔 0.5~1.5s
    │                        • 重试3次
    ▼                        • 返回评论列表
  返回结构化数据
  （与 Python 版格式一致）
```

**关键设计决策**

| 决策点 | 实现方式 | 效果 |
|--------|----------|------|
| **统一返回格式** | `_cpp_comment_to_bilibili_format()` 转换 C++ 扁平结构 | 上层 `save_comment()` 无需感知数据来源差异 |
| **超时配置** | C++ 服务 timeout=300s，Python 重试间隔递增 | 防止长时间等待失败请求 |
| **评论分页** | B站游标 API（`cursor.next`），非旧版 page 参数 | 支持全量爬取，不受单页上限限制 |
| **反风控间隔** | Python Fallback 加随机 0.5~1.5s 间隔 | 降低 B站风控触发概率 |

### 3.2 前端技术栈

| 技术 | 版本 | 用途 |
|-----|-----|-----|
| Electron | 25+ | 桌面应用框架 |
| Vue.js | 3.3+ | UI框架 |
| ECharts | 5.4+ | 数据可视化 |
| WebSocket | - | 实时通信 |
| Axios | 1.13+ | HTTP客户端 |

### 3.3 基础设施

| 技术 | 用途 |
|-----|-----|
| Nginx | 反向代理、负载均衡 |
| Supervisor | 进程管理 |
| systemd | 服务自启动 |

---

## 4. 核心模块实现

### 4.1 Chrome扩展模块

**文件位置**：`/chrome_extension/`

**核心功能**：
- 监控B站页面的视频变化
- 从URL中提取BV号
- 通过WebSocket实时通知悬浮窗口

**关键代码结构**：

```javascript
// content.js - 视频监控器
class BilibiliVideoMonitor {
    constructor() {
        this.socket = null;
        this.lastBvId = null;
        this.reconnectAttempts = 0;
        this.reconnectDelay = 2000; // 初始重连间隔 2秒
        this.init();
    }

    // 连接到悬浮窗口的WebSocket服务器
    connectWebSocket() {
        this.socket = new WebSocket('ws://localhost:3000');
        // 处理连接、消息、断连、重连逻辑
    }

    // 开始监控视频变化
    startMonitoring() {
        this.monitorInterval = setInterval(() => {
            this.checkVideoChange();
        }, 2000);
    }

    // 从URL中提取BV号
    extractBvId(url) {
        const patterns = [
            /video\/(BV[a-zA-Z0-9]+)/,  // 标准视频页面
            /BV([a-zA-Z0-9]+)/,         // 其他页面中的BV号
        ];
        // 返回提取的BV号
    }
}
```

**技术亮点**：
1. **指数退避重连**：网络断开时采用2s→4s→8s→16s的指数退避策略，最长30s间隔
2. **多URL格式支持**：支持标准视频页、分享链接、短链接等多种URL格式
3. **最小化资源消耗**：仅使用2秒轮询，不影响页面性能

### 4.2 Electron悬浮窗口模块

**文件位置**：`/electron/`

**核心功能**：
- 桌面端悬浮窗展示
- 多窗口管理（主窗口、情感分析、用户画像、音频分析等）
- WebSocket服务端（接收Chrome扩展消息）
- HTTP通知服务器（接收Django后端任务完成通知）

**主窗口特性**：

```javascript
// main.js - 窗口创建配置
mainWindow = new BrowserWindow({
    width: 600,
    height: 712,
    frame: false,           // 无边框窗口
    alwaysOnTop: true,      // 始终置顶
    transparent: true,      // 透明背景
    resizable: false,       // 禁止调整大小
    skipTaskbar: false,     // 显示在任务栏
    backgroundColor: '#00000000', // 完全透明背景
    webPreferences: {
        nodeIntegration: true,
        contextIsolation: false,
        webSecurity: false,  // 允许跨域请求
        partition: 'persist:main'  // 持久化cookie共享
    }
});
```

**多窗口架构**：

| 窗口 | 文件 | 功能 |
|-----|------|-----|
| 主窗口 | index.html | 悬浮球界面，快速查看当前视频情感 |
| 情感分析 | emotional-analysis.html | 详细情感分布图表 |
| 用户画像 | user-profile.html | 用户评论者画像分析 |
| 音频分析 | video-audio-analysis.html | 视频音频情感分析 |
| 总体报告 | overall-reports.html | 多模态融合分析报告 |
| 展开视图 | expanded-view.html | 展开的全屏仪表盘 |

**技术亮点**：
1. **透明悬浮设计**：使用CSS backdrop-filter实现毛玻璃效果
2. **智能窗口定位**：默认在鼠标位置附近打开，可记忆上次位置
3. **窗口层级管理**：失去焦点后自动重设置顶层级
4. **系统托盘**：支持最小化到系统托盘

### 4.3 Django后端模块

**文件位置**：`/analysis/`

#### 4.3.1 视图层 (views.py)

提供REST API接口，处理前端请求：

```python
# 核心API接口
@csrf_exempt
def analyze_by_bvid(request):
    """根据BV号分析视频情感"""
    # 获取请求参数
    # 调用服务层处理
    # 返回JSON响应

@csrf_exempt
def async_analyze_video(request):
    """并发分析视频接口 - 立即返回任务状态"""
    # 触发Celery异步任务
    # 返回任务ID供前端轮询
```

#### 4.3.2 服务层 (services.py)

业务逻辑处理的核心：

```python
def process_video(bvid, headers, cookie):
    """处理视频分析主流程"""
    # 1. 检查缓存
    # 2. 爬取视频信息
    # 3. 爬取评论数据
    # 4. 执行情感分析
    # 5. 保存结果到数据库

def crawl_video_info(bvid, headers):
    """爬取视频基本信息"""

def crawl_comments(bvid, headers, cookie):
    """爬取视频评论"""
```

#### 4.3.3 任务层 (tasks.py)

Celery异步任务定义：

```python
@celery_app.task(bind=True)
def crawl_and_analyze_comments(self, bvid, cookie):
    """异步爬取并分析评论"""
    # 进度推送
    self.update_state(state='PROGRESS', meta={'progress': 0})
    # 分页爬取评论
    # 批量情感分析
    # 保存结果

@celery_app.task
def crawl_and_analyze_danmu(bvid):
    """异步爬取并分析弹幕"""

@celery_app.task
def analyze_audio_task(bvid):
    """异步分析音频情感"""
```

### 4.4 C++爬虫服务模块

**文件位置**：`/crawler_service/`

**技术选型**：
- libcurl：HTTP/HTTPS请求
- nlohmann/json：JSON解析
- pugixml：XML解析（弹幕格式）

**核心功能**：

```cpp
// crawler.h - 爬虫类定义
class Crawler {
public:
    Crawler(const Config& cfg);
    ~Crawler();

    // 视频信息爬取
    std::string crawl_video_info(const std::string& bvid);

    // 评论爬取
    std::string crawl_comments(const std::string& bvid, int64_t next_offset);

    // 弹幕爬取
    std::string crawl_danmu(const std::string& cid);

    // 代理池管理
    std::string get_next_proxy();
    void remove_failed_proxy(const std::string& proxy);

private:
    Config config_;
    std::string current_proxy_;
    std::vector<std::string> proxy_pool_;
};
```

**WBI签名实现**：

B站API需要WBI签名，本项目实现了C++版本的WBI签名器：

```cpp
// wbi_signer.h - WBI签名器
class WbiSigner {
public:
    static WbiSigner& get_instance();

    // 设置SESSDATA API地址
    void set_sessdata_api(const std::string& base_url, const std::string& api_path);

    // 获取签名后的请求头
    std::map<std::string, std::string> get_signed_headers();

    // WBI签名算法实现
    std::string sign_request(const std::string& params);
};
```

**代理池机制**：

1. **独享代理**：预先购买的专用代理，稳定性高
2. **短效代理**：动态获取的短效代理，成本低
3. **自动切换**：请求失败自动切换代理
4. **失败移除**：连续失败从代理池移除

```cpp
// 代理池管理
std::string Crawler::get_next_proxy() {
    // 优先使用独享代理
    // 独享代理用尽后使用短效代理
    // 失败后自动切换
}
```

### 4.5 情感分析模块

**文件位置**：`/analysis/sentiment_model.py`

本系统的情感分析模块采用多层次、多模态的架构设计，支持文本评论情感分析、弹幕情感分析和音频情感分析三大核心能力。

#### 4.5.1 文本情感分析

本系统使用ONNX格式的BERT模型进行中文文本情感分析。文本情感分析是整个系统的基础模块，负责对视频评论进行正面、中性、负面三类情感分类。

**模型架构详解**：

```
输入文本 → 分词(Tokenization) → 嵌入(Embedding) → BERT编码器 × 12层 → 池化 → 分类头 情感标签 →
```

**核心技术要点**：

1. **模型选择**：使用中文预训练模型 `bert-base-chinese`，12层Transformer编码器，隐藏层维度768
2. **模型转换**：将PyTorch模型导出为ONNX格式，支持跨平台推理
3. **批量推理**：支持批量处理32/64/128条评论，利用向量化加速
4. **动态批处理**：根据文本长度自动分组，减少填充(Padding)开销

```python
class SentimentModel:
    """单例模式的情感分析模型"""

    def __init__(self, model_path=None):
        # 加载ONNX模型
        self.session = ort.InferenceSession(model_path)
        # 获取模型输入输出名称
        self.input_names = [input.name for input in self.session.get_inputs()]
        self.output_names = [output.name for output in self.session.get_outputs()]
        # 加载BERT分词器
        self.tokenizer = BertTokenizer.from_pretrained(tokenizer_dir)
        # 加载情感标签映射
        self.label_map = {0: "negative", 1: "neutral", 2: "positive"}

    def predict(self, text_list, batch_size=32):
        """批量预测文本情感"""
        results = []
        for i in range(0, len(text_list), batch_size):
            batch = text_list[i:i + batch_size]
            # 1. 编码与对齐
            inputs = self.tokenizer(batch, padding=True, truncation=True, max_length=128, return_tensors='np')
            # 2. ONNX推理
            ort_inputs = {name: inputs[name] for name in self.input_names}
            logits = self.session.run(self.output_names, ort_inputs)[0]
            # 3. Softmax获取各情感概率
            probs = softmax(logits, axis=1)
            # 4. 获取预测标签和置信度
            for prob in probs:
                label_id = np.argmax(prob)
                results.append({
                    'label': self.label_map[label_id],
                    'score': float(prob[label_id]),
                    'probabilities': {
                        'positive': float(prob[2]),
                        'neutral': float(prob[1]),
                        'negative': float(prob[0])
                    }
                })
        return results
```

**模型训练配置**：

| 参数 | 值 | 说明 |
|-----|-----|-----|
| 模型架构 | BERT-base-chinese | 12层Transformer |
| 隐藏层维度 | 768 | 标准BERT配置 |
| 注意力头数 | 12 | 多头自注意力 |
| 最大序列长度 | 128 | 评论文本长度 |
| 预训练数据 | 中文维基百科+百度百科 | 16GB中文语料 |
| 微调数据集 | 30万条标注评论 | 正/中/负各10万 |
| 训练轮次 | 5 epochs | early stopping |
| 学习率 | 2e-5 | BERT标准学习率 |
| 批量大小 | 32 | GPU显存限制 |
| 优化器 | AdamW | 权重衰减0.01 |

**模型格式**：ONNX (Open Neural Network Exchange)
- 跨平台推理：支持Windows/Linux/Mac/Android/iOS
- 无需PyTorch依赖：运行时仅需ONNX Runtime
- 高性能推理：比PyTorch快30%-50%
- 量化支持：可选INT8量化进一步加速

#### 4.5.2 弹幕情感分析

弹幕情感分析与文本评论类似，但由于弹幕具有以下特点，需要专门处理：

1. **短文本为主**：弹幕通常只有几个字到几十个字
2. **网络用语多**：大量缩写、梗、颜文字
3. **噪声较高**：需要过滤无效弹幕

```python
class DanmuSentimentModel:
    """弹幕情感分析模型"""

    def __init__(self):
        # 加载专用弹幕情感模型（比评论模型更轻量）
        self.session = ort.InferenceSession(danmu_model_path)
        self.tokenizer = BertTokenizer.from_pretrained(danmu_tokenizer_dir)

    def preprocess(self, danmu_list):
        """弹幕预处理"""
        processed = []
        for danmu in danmu_list:
            # 1. 去除特殊弹幕（系统弹幕、广告弹幕）
            if self.is_system_danmu(danmu):
                continue
            # 2. 颜文字情感倾向提取
            danmu = self.process_emoticon(danmu)
            # 3. 过滤超长弹幕
            danmu = danmu[:128]
            processed.append(danmu)
        return processed

    def is_system_danmu(self, text):
        """判断是否为系统弹幕"""
        system_patterns = ['弹幕高能', '前方高能', '声明', '转载', '广告']
        return any(p in text for p in system_patterns)

    def process_emoticon(self, text):
        """处理颜文字情感"""
        # 颜文字情感词典
        emoticon_sentiment = {
            '(๑•̀ㅂ•́)و': 0.9,
            '(◕ᴗ◕✿)': 0.8,
            '(ಥ﹏ಥ)': 0.2,
            'QAQ': 0.2,
        }
        # 替换颜文字为情感分数
        for emo, score in emoticon_sentiment.items():
            if emo in text:
                text = text.replace(emo, '')
        return text
```

#### 4.5.3 音频情感分析

使用BiLSTM模型进行音频情感分类。音频情感分析是本系统的特色功能，能够分析视频中语音内容的情感倾向。

**音频情感分析流程**：

```
音频文件 → 分段(15秒/段) → 特征提取(MFCC+梅尔频谱+色度) → BiLSTM编码 → 全连接分类 → 情感标签
```

**特征工程详解**：

1. **MFCC特征（Mel-frequency cepstral coefficients）**
   - 提取13维MFCC系数
   - 反映语音的短时功率谱包络
   - 对噪声有较好的鲁棒性

2. **梅尔频谱（Mel Spectrogram）**
   - 128维梅尔滤波器组输出
   - 时频分辨率：50ms帧长，10ms帧移
   - 捕捉语音的频谱变化

3. **色度特征（Chroma）**
   - 12维色度向量
   - 反映音高分布
   - 对音乐类视频特别有效

```python
class AudioSentimentModel:
    """音频情感分析模型"""

    # 音频分段参数
    SEGMENT_DURATION = 15  # 每段15秒
    OVERLAP = 5           # 重叠5秒

    # 支持的情感类别
    EMOTION_LABELS = ['angry', 'fearful', 'happy', 'neutral', 'sad', 'surprise']

    def __init__(self, model_path=None):
        # 加载BiLSTM ONNX模型
        self.session = ort.InferenceSession(model_path)
        # 特征标准化参数
        self.feature_mean = np.load('models/audio/feature_mean.npy')
        self.feature_std = np.load('models/audio/feature_std.npy')

    def extract_features(self, audio_data, sample_rate=16000):
        """提取音频特征"""
        features = {}

        # 1. MFCC特征 (13维)
        mfcc = librosa.feature.mfcc(y=audio_data, sr=sample_rate, n_mfcc=13)
        features['mfcc'] = mfcc

        # 2. 梅尔频谱 (128维)
        mel_spec = librosa.feature.melspectrogram(y=audio_data, sr=sample_rate, n_mels=128)
        mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)
        features['mel_spec'] = mel_spec_db

        # 3. 色度特征 (12维)
        chroma = librosa.feature.chroma_stft(y=audio_data, sr=sample_rate)
        features['chroma'] = chroma

        # 4. 频谱对比度 (6维)
        contrast = librosa.feature.spectral_contrast(y=audio_data, sr=sample_rate)
        features['contrast'] = contrast

        # 5. 零交叉率 (1维)
        zcr = librosa.feature.zero_crossing_rate(audio_data)
        features['zcr'] = zcr

        # 6. 梅尔频率倒谱系数 delta (13维)
        mfcc_delta = librosa.feature.delta(mfcc)
        features['mfcc_delta'] = mfcc_delta

        # 合并所有特征
        combined_features = np.concatenate([
            np.mean(mfcc, axis=1),
            np.mean(mel_spec_db, axis=1),
            np.mean(chroma, axis=1),
            np.mean(contrast, axis=1),
            np.mean(zcr, axis=1),
            np.mean(mfcc_delta, axis=1)
        ])

        return combined_features

    def segment_audio(self, audio_path):
        """音频分段"""
        audio_data, sr = librosa.load(audio_path, sr=16000)
        segments = []
        for start in range(0, int(audio_data.shape[0]), self.SEGMENT_DURATION * sr - self.OVERLAP * sr):
            end = start + self.SEGMENT_DURATION * sr
            if end > audio_data.shape[0]:
                break
            segment = audio_data[start:end]
            segments.append(segment)
        return segments

    def predict(self, audio_path):
        """预测音频情感"""
        # 分段处理
        segments = self.segment_audio(audio_path)

        results = []
        for segment in segments:
        # 提取特征
            features = self.extract_features(segment)

            # 标准化
            features = (features - self.feature_mean) / self.feature_std
            features = features.reshape(1, -1)

        # ONNX推理
            logits = self.session.run(None, {'input': features})[0]

            # Softmax获取概率
            probs = softmax(logits, axis=1)[0]

            # 获取情感标签
            emotion_id = np.argmax(probs)
            emotion = self.EMOTION_LABELS[emotion_id]

            results.append({
                'emotion': emotion,
                'confidence': float(probs[emotion_id]),
                'probabilities': {label: float(prob) for label, prob in zip(self.EMOTION_LABELS, probs)}
            })

        return results
```

**BiLSTM模型架构**：

```
输入层 (173维特征)
    ↓
BiLSTM (128隐藏单元, 2层)
    ↓
Dropout (0.3)
    ↓
全连接层 (64)
    ↓
Dropout (0.3)
    ↓
输出层 (6类情感)
```

**音频情感模型训练配置**：

| 参数 | 值 | 说明 |
|-----|-----|-----|
| 模型架构 | BiLSTM | 2层, 128隐藏单元 |
| 输入特征 | 173维 | MFCC+梅尔+色度+对比度+ZCR+Delta |
| 隐藏层单元 | 128 | 双向LSTM |
| 层数 | 2 | 堆叠LSTM |
| Dropout | 0.3 | 防止过拟合 |
| 训练数据 | 50小时标注语音 | IEMOCAP + 自建数据集 |
| 采样率 | 16000 Hz | 统一音频采样率 |
| 分段长度 | 15秒 | 滑动窗口 |

**支持的情感类别**：
- angry（愤怒）
- fearful（恐惧）
- happy（开心）
- neutral（中性）
- sad（悲伤）
- surprise（惊讶）

### 4.6 多模态融合模块

**文件位置**：`/analysis/multimodal_attention.py`

实现文本、弹幕、音频三种模态的情感融合：

```python
class MultimodalFusion:
    """多模态情感融合"""

    def __init__(self):
        # 加载各模态权重
        self.audio_weight = 0.35
        self.text_weight = 0.35
        self.danmu_weight = 0.30

    def fuse(self, text_emotion, audio_emotion, danmu_emotion):
        """加权融合各模态情感"""
        fused = {}
        for label in ['positive', 'neutral', 'negative']:
            fused[label] = (
                text_emotion[label] * self.text_weight +
                audio_emotion[label] * self.audio_weight +
                danmu_emotion[label] * self.danmu_weight
            )
        return fused

    def detect_conflict(self, text_emotion, audio_emotion):
        """检测情感冲突"""
        # 计算各模态情感差异
        # 判断是否存在显著冲突
```

---

## 5. 数据模型设计

本节使用 **逻辑数据模型 E-R 图** 和 **数据字典** 描述系统存储的长期数据及数据库结构。系统采用 MySQL 作为关系型数据库，使用 Django ORM 管理数据对象与迁移。

### 5.1 逻辑数据模型（E-R 图）

系统涉及 9 个核心实体，实体间通过外键建立关联。E-R 图如下所示（采用 Chen 表示法，矩形为实体，菱形为关系，椭圆为属性）：

```
                                    ┌─────────────────┐
                                    │   User（用户）   │
                                    │ id(PK)          │
                                    │ username        │
                                    │ email           │
                                    │ sessdata        │
                                    │ bilibili_mid    │
                                    └────────┬────────┘
                                             │
                         ┌───────────────────┼───────────────────┐
                         │ 1                 │ 1                 │
                         │                   │                   │
                         ▼ N                 ▼ N                 │
              ┌──────────────────┐  ┌────────────────────────────┐
              │UserVideoHistory  │  │  UserConfig（用户配置）     │
              │ 用户视频历史      │  │  id(PK), min_length, ...   │
              │ user_id(FK)      │  │  单例模式，仅一条记录       │
              │ video_id(FK)     │  └────────────────────────────┘
              │ analyzed_at      │
              │ is_favorite      │
              └────────┬─────────┘
                       │ N
                       │
                       │ 1
              ┌────────▼─────────┐
              │  Video（视频）    │
              │ bvid(PK)         │
              │ aid(UK), cid     │
              │ title, pubdate   │
              │ view, like, ...  │
              └────────┬─────────┘
         ┌─────────────┼─────────────┬─────────────────┬────────────────────┐
         │ 1           │ 1           │ 1               │ 1                  │
         │             │             │                 │                    │
         ▼ N           ▼ N           ▼ 1               ▼ N                  │
┌──────────────┐ ┌──────────────┐ ┌─────────────────┐ ┌──────────────────────┐
│  Comment     │ │   Danmu      │ │MultimodalSentiment│ │  AudioSentiment      │
│  评论表      │ │  弹幕表      │ │ 多模态情感融合   │ │  音频情感分段        │
│ rpid(PK)     │ │ id(PK,自增)  │ │ video_id(FK,UK) │ │ id(PK), video_id(FK) │
│ video_id(FK) │ │ cid(索引)    │ │ fused_*         │ │ time_offset          │
│ mid, uname   │ │ video_time   │ │ audio_weight    │ │ sentiment_score      │
│ message      │ │ content      │ │ text_emotion    │ │ emotion_probs(JSON)  │
│ sentiment_*  │ │ sentiment_*  │ │ has_conflict    │ │ segment_duration    │
└──────────────┘ └──────────────┘ └─────────────────┘ └──────────────────────┘

                                    ┌─────────────────────────┐
                                    │ EmailVerificationCode   │
                                    │ 邮箱验证码              │
                                    │ id(PK), email, code    │
                                    │ purpose, expires_at    │
                                    └─────────────────────────┘
```

**实体关系说明**

| 关系 | 类型 | 说明 |
|------|------|------|
| User — UserVideoHistory | 1:N | 一用户可有多条分析历史 |
| Video — UserVideoHistory | 1:N | 一视频可被多用户分析 |
| Video — Comment | 1:N | 一视频对应多条评论 |
| Video — Danmu | 1:N | 通过 `cid` 关联，一视频对应多条弹幕 |
| Video — AudioSentiment | 1:N | 一视频对应多段音频情感 |
| Video — MultimodalSentiment | 1:1 | 一视频对应一条多模态融合结果 |
| User — UserConfig | 1:1 | 全局配置单例（User 表内也存用户级配置） |

### 5.2 数据字典

以下按表列出各字段的**字段名称、字段描述、数据类型、长度、是否允许空、缺省值、备注**（主键、外键、索引等），格式与标准数据字典一致。

---

#### 表1：视频信息表（videos）

| 字段名称 | 字段描述 | 数据类型 | 长度 | 是否允许空 | 缺省值 | 备注 |
|----------|----------|----------|------|------------|--------|------|
| bvid | 视频BV号 | varchar | 20 | N | - | **主键** |
| aid | 视频AV号 | bigint | - | N | - | **唯一索引** |
| cid | 弹幕/分P ID | bigint | - | Y | NULL | - |
| title | 视频标题 | varchar | 255 | Y | NULL | - |
| pubdate | 发布日期 | datetime | - | Y | NULL | - |
| raw_comment_count | 原始爬取评论数 | int | - | N | 0 | - |
| view | 播放量 | bigint | - | N | 0 | - |
| like | 点赞数 | bigint | - | N | 0 | - |
| coin | 投币数 | bigint | - | N | 0 | - |
| favorite | 收藏数 | bigint | - | N | 0 | - |
| share | 分享数 | bigint | - | N | 0 | - |

---

#### 表2：评论表（comments）

| 字段名称 | 字段描述 | 数据类型 | 长度 | 是否允许空 | 缺省值 | 备注 |
|----------|----------|----------|------|------------|--------|------|
| rpid | 评论ID | bigint | - | N | - | **主键** |
| video_id | 所属视频BV号 | varchar | 20 | N | - | **外键**→videos.bvid |
| mid | 用户UID | bigint | - | N | - | **索引** |
| uname | 用户名 | varchar | 100 | Y | NULL | - |
| message | 评论正文 | text | - | N | - | - |
| like_count | 点赞数 | int | - | N | 0 | - |
| reply_count | 回复/子评论数 | int | - | N | 0 | - |
| location | IP属地 | varchar | 50 | Y | NULL | - |
| ctime | 发布时间 | datetime | - | Y | NULL | - |
| vip_type | 会员类型 | int | - | N | 0 | - |
| vip_label | 会员标签 | varchar | 50 | Y | NULL | - |
| user_level | 用户等级 | int | - | N | 0 | - |
| parent_rpid | 父评论ID | bigint | - | N | 0 | - |
| sentiment_score | 情感得分(0~1) | float | - | N | 0.5 | - |
| sentiment_label | 情感分类 | varchar | 10 | N | 'neutral' | positive/neutral/negative |
| quality_score | 质量评分 | float | - | N | 0.5 | - |
| is_duplicate | 是否重复 | tinyint | - | N | 0 | - |
| duplicate_group | 重复组ID | varchar | 100 | Y | NULL | - |

---

#### 表3：弹幕表（danmus）

| 字段名称 | 字段描述 | 数据类型 | 长度 | 是否允许空 | 缺省值 | 备注 |
|----------|----------|----------|------|------------|--------|------|
| id | 自增主键 | bigint | - | N | - | **主键**，自增 |
| cid | 关联视频CID | bigint | - | N | - | **索引**，与 videos.cid 对应 |
| video_time | 视频内出现时间(秒) | float | - | N | 0 | - |
| content | 弹幕内容 | text | - | N | - | - |
| send_time | 真实发送时间 | datetime | - | Y | NULL | - |
| user_hash | 发送者Hash值 | varchar | 20 | Y | NULL | - |
| sentiment_score | 情感得分 | float | - | N | 0.5 | - |
| sentiment_label | 情感分类 | varchar | 10 | N | 'neutral' | - |
| quality_score | 质量评分 | float | - | N | 0.5 | - |
| is_duplicate | 是否重复 | tinyint | - | N | 0 | - |
| duplicate_group | 重复组ID | varchar | 100 | Y | NULL | - |

---

#### 表4：音频情感表（audio_sentiments）

| 字段名称 | 字段描述 | 数据类型 | 长度 | 是否允许空 | 缺省值 | 备注 |
|----------|----------|----------|------|------------|--------|------|
| id | 自增主键 | bigint | - | N | - | **主键**，自增 |
| video_id | 所属视频BV号 | varchar | 20 | N | - | **外键**→videos.bvid |
| time_offset | 视频内时间偏移(秒) | float | - | N | - | - |
| sentiment_score | 情感极性得分(0~1) | float | - | N | 0.5 | - |
| sentiment_label | 情感分类 | varchar | 10 | N | 'neutral' | - |
| emotion_probs | 各情感概率分布 | json | - | N | {} | 如 {happy:0.8,sad:0.1,...} |
| segment_duration | 分段时长(秒) | float | - | N | 15 | - |
| text_transcript | ASR转录文本 | text | - | Y | NULL | 预留字段 |

---

#### 表5：多模态情感融合表（multimodal_sentiments）

| 字段名称 | 字段描述 | 数据类型 | 长度 | 是否允许空 | 缺省值 | 备注 |
|----------|----------|----------|------|------------|--------|------|
| id | 自增主键 | bigint | - | N | - | **主键**，自增 |
| video_id | 所属视频BV号 | varchar | 20 | N | - | **外键**→videos.bvid，**唯一** |
| fused_positive | 融合正面概率 | float | - | N | 0.33 | - |
| fused_neutral | 融合中性概率 | float | - | N | 0.33 | - |
| fused_negative | 融合负面概率 | float | - | N | 0.34 | - |
| audio_weight | 音频模态权重 | float | - | N | 0.35 | - |
| text_weight | 文本模态权重 | float | - | N | 0.35 | - |
| danmu_weight | 弹幕模态权重 | float | - | N | 0.3 | - |
| audio_emotion | 音频情感分布 | json | - | N | {} | - |
| text_emotion | 文本情感分布 | json | - | N | {} | - |
| danmu_emotion | 弹幕情感分布 | json | - | N | {} | - |
| has_conflict | 是否存在情感冲突 | tinyint | - | N | 0 | - |
| conflict_details | 冲突详情 | json | - | N | [] | - |
| video_type | 视频类型 | varchar | 20 | N | 'general' | music/tutorial/vlog/game |
| dominant_emotion | 主导情感 | varchar | 20 | N | 'neutral' | - |
| emotion_strength | 情感强度 | float | - | N | 0 | - |
| overall_score | 综合得分 | float | - | N | 0.5 | - |
| analyzed_at | 分析时间 | datetime | - | N | 当前时间 | auto_now |

---

#### 表6：用户表（users）

| 字段名称 | 字段描述 | 数据类型 | 长度 | 是否允许空 | 缺省值 | 备注 |
|----------|----------|----------|------|------------|--------|------|
| id | 用户ID | bigint | - | N | - | **主键**，自增 |
| username | 用户名 | varchar | 150 | N | - | **唯一** |
| email | 邮箱 | varchar | 254 | Y | NULL | - |
| password | 密码哈希 | varchar | 128 | N | - | - |
| bilibili_mid | B站用户ID | bigint | - | Y | NULL | - |
| sessdata | B站SESSDATA | text | - | Y | NULL | - |
| bili_jct | B站BILI_JCT | varchar | 50 | Y | NULL | - |
| refresh_token | B站刷新令牌 | varchar | 100 | Y | NULL | - |
| access_token | B站访问令牌 | varchar | 100 | Y | NULL | - |
| min_length | 最小文本长度 | int | - | N | 1 | 过滤配置 |
| max_length | 最大文本长度 | int | - | N | 500 | - |
| min_chinese_ratio | 最小中文占比 | float | - | N | 0.15 | - |
| min_quality_score | 最小质量评分 | float | - | N | 0.2 | - |
| dedup_method | 去重方法 | varchar | 20 | N | 'exact' | exact/fuzzy/embedding |
| fuzzy_threshold | 模糊去重阈值 | float | - | N | 0.85 | - |
| embedding_threshold | 语义去重阈值 | float | - | N | 0.85 | - |
| max_char_repeat | 单字符最大重复 | int | - | N | 10 | - |
| min_unique_ratio | 最小字符多样性 | float | - | N | 0.2 | - |
| min_unique_check_length | 多样性检查长度 | int | - | N | 15 | - |
| high_like_threshold | 高赞阈值 | int | - | N | 50 | - |
| high_reply_threshold | 热门讨论阈值 | int | - | N | 10 | - |
| combined_like_threshold | 综合热度-点赞 | int | - | N | 20 | - |
| combined_reply_threshold | 综合热度-回复 | int | - | N | 5 | - |
| background_color | 背景颜色 | varchar | 7 | N | '#1a1a2e' | - |
| opacity | 透明度 | float | - | N | 0.95 | - |
| is_active | 是否激活 | tinyint | - | N | 1 | Django 内置 |
| date_joined | 注册时间 | datetime | - | N | - | Django 内置 |
| last_login | 最后登录 | datetime | - | Y | NULL | Django 内置 |

---

#### 表7：用户视频历史表（user_video_history）

| 字段名称 | 字段描述 | 数据类型 | 长度 | 是否允许空 | 缺省值 | 备注 |
|----------|----------|----------|------|------------|--------|------|
| id | 自增主键 | bigint | - | N | - | **主键**，自增 |
| user_id | 用户ID | bigint | - | N | - | **外键**→users.id |
| video_id | 视频BV号 | varchar | 20 | N | - | **外键**→videos.bvid |
| analyzed_at | 最后分析时间 | datetime | - | N | 当前时间 | - |
| is_favorite | 是否收藏 | tinyint | - | N | 0 | - |
| note | 备注 | varchar | 255 | Y | NULL | - |

**约束**：`(user_id, video_id)` **唯一**，同一用户对同一视频仅一条历史记录。

---

#### 表8：用户配置表（user_config）

| 字段名称 | 字段描述 | 数据类型 | 长度 | 是否允许空 | 缺省值 | 备注 |
|----------|----------|----------|------|------------|--------|------|
| id | 配置ID | bigint | - | N | 1 | **主键**，单例固定为1 |
| min_length | 最小文本长度 | int | - | N | 1 | - |
| max_length | 最大文本长度 | int | - | N | 500 | - |
| min_chinese_ratio | 最小中文占比 | float | - | N | 0.15 | - |
| min_quality_score | 最小质量评分 | float | - | N | 0.2 | - |
| dedup_method | 去重方法 | varchar | 20 | N | 'exact' | - |
| fuzzy_threshold | 模糊去重阈值 | float | - | N | 0.85 | - |
| embedding_threshold | 语义去重阈值 | float | - | N | 0.85 | - |
| max_char_repeat | 单字符最大重复 | int | - | N | 10 | - |
| min_unique_ratio | 最小字符多样性 | float | - | N | 0.2 | - |
| min_unique_check_length | 多样性检查长度 | int | - | N | 15 | - |
| high_like_threshold | 高赞阈值 | int | - | N | 50 | - |
| high_reply_threshold | 热门讨论阈值 | int | - | N | 10 | - |
| combined_like_threshold | 综合热度-点赞 | int | - | N | 20 | - |
| combined_reply_threshold | 综合热度-回复 | int | - | N | 5 | - |
| background_color | 背景颜色 | varchar | 7 | N | '#1a1a2e' | - |
| opacity | 透明度 | float | - | N | 0.95 | - |
| updated_at | 更新时间 | datetime | - | N | 当前时间 | auto_now |

---

#### 表9：邮箱验证码表（email_verification_codes）

| 字段名称 | 字段描述 | 数据类型 | 长度 | 是否允许空 | 缺省值 | 备注 |
|----------|----------|----------|------|------------|--------|------|
| id | 自增主键 | bigint | - | N | - | **主键**，自增 |
| email | 邮箱地址 | varchar | 254 | N | - | - |
| code | 验证码 | varchar | 6 | N | - | - |
| purpose | 用途 | varchar | 20 | N | 'register' | register/reset_password |
| created_at | 创建时间 | datetime | - | N | - | - |
| expires_at | 过期时间 | datetime | - | N | - | - |
| is_used | 是否已使用 | tinyint | - | N | 0 | - |

---

### 5.3 核心数据表（ORM 定义）

以下为 Django ORM 模型定义，对应上述数据字典。数据库表结构由 Django Migration 自动生成，实际表名见 `db_table`。

#### 5.3.1 视频表 (videos)

```python
class Video(models.Model):
    bvid = models.CharField(max_length=20, primary_key=True)   # BV号
    aid = models.BigIntegerField(unique=True)                  # AV号
    cid = models.BigIntegerField(null=True)                   # 弹幕/分P ID
    title = models.CharField(max_length=255, null=True)       # 标题
    pubdate = models.DateTimeField(null=True)                  # 发布日期
    raw_comment_count = models.IntegerField(default=0)         # 原始评论数
    view = models.BigIntegerField(default=0)                  # 播放量
    like = models.BigIntegerField(default=0)                  # 点赞数
    coin = models.BigIntegerField(default=0)                  # 投币数
    favorite = models.BigIntegerField(default=0)               # 收藏数
    share = models.BigIntegerField(default=0)                  # 分享数
```

##### 5.3.2 评论表 (comments)

```python
class Comment(models.Model):
    rpid = models.BigIntegerField(primary_key=True)          # 评论ID
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    mid = models.BigIntegerField(db_index=True)              # 用户UID
    uname = models.CharField(max_length=100, null=True)      # 用户名
    message = models.TextField()                              # 评论正文
    like_count = models.IntegerField(default=0)              # 点赞数
    reply_count = models.IntegerField(default=0)              # 回复/子评论数
    location = models.CharField(max_length=50, null=True)     # IP属地
    ctime = models.DateTimeField(null=True)                   # 发布时间
    vip_type = models.IntegerField(default=0)                # 会员类型
    vip_label = models.CharField(max_length=50, null=True)    # 会员标签
    user_level = models.IntegerField(default=0)              # 用户等级
    parent_rpid = models.BigIntegerField(default=0)           # 父评论ID
    sentiment_score = models.FloatField(default=0.5)          # 情感得分(0~1)
    sentiment_label = models.CharField(max_length=10, default="neutral")
    quality_score = models.FloatField(default=0.5)            # 质量评分
    is_duplicate = models.BooleanField(default=False)        # 是否重复
    duplicate_group = models.CharField(max_length=100, null=True)
```

##### 5.3.3 弹幕表 (danmus)

```python
class Danmu(models.Model):
    cid = models.BigIntegerField(db_index=True)              # 关联视频CID
    video_time = models.FloatField(default=0)                # 视频内出现时间(秒)
    content = models.TextField()                             # 弹幕内容
    send_time = models.DateTimeField(null=True)              # 发送时间
    user_hash = models.CharField(max_length=20, null=True)  # 发送者Hash
    sentiment_score = models.FloatField(default=0.5)         # 情感得分
    sentiment_label = models.CharField(max_length=10, default="neutral")
    quality_score = models.FloatField(default=0.5)            # 质量评分
    is_duplicate = models.BooleanField(default=False)       # 是否重复
    duplicate_group = models.CharField(max_length=100, null=True)
```

##### 5.3.4 音频情感表 (audio_sentiments)

```python
class AudioSentiment(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    time_offset = models.FloatField()                        # 视频内时间偏移(秒)
    sentiment_score = models.FloatField(default=0.5)       # 情感极性(0~1)
    sentiment_label = models.CharField(max_length=10, default="neutral")
    emotion_probs = models.JSONField(default=dict)            # 6类情感概率分布
    segment_duration = models.FloatField(default=15)         # 分段时长(秒)
    text_transcript = models.TextField(null=True)            # ASR转录文本（预留）
```

##### 5.3.5 多模态融合表 (multimodal_sentiments)

```python
class MultimodalSentiment(models.Model):
    video = models.OneToOneField(Video, on_delete=models.CASCADE)
    fused_positive = models.FloatField(default=0.33)   # 融合正面概率
    fused_neutral = models.FloatField(default=0.33)    # 融合中性概率
    fused_negative = models.FloatField(default=0.34)   # 融合负面概率
    audio_weight = models.FloatField(default=0.35)     # 音频权重
    text_weight = models.FloatField(default=0.35)      # 文本权重
    danmu_weight = models.FloatField(default=0.3)      # 弹幕权重
    audio_emotion = models.JSONField(default=dict)     # 音频情感分布
    text_emotion = models.JSONField(default=dict)      # 文本情感分布
    danmu_emotion = models.JSONField(default=dict)     # 弹幕情感分布
    has_conflict = models.BooleanField(default=False)   # 是否冲突
    conflict_details = models.JSONField(default=list)   # 冲突详情
    video_type = models.CharField(max_length=20, default='general')
    dominant_emotion = models.CharField(max_length=20, default='neutral')
    emotion_strength = models.FloatField(default=0.0)    # 情感强度
    overall_score = models.FloatField(default=0.5)       # 综合得分
    analyzed_at = models.DateTimeField(auto_now=True)    # 分析时间
```

##### 5.3.6 用户表 (users)

```python
class User(AbstractUser):
    bilibili_mid = models.BigIntegerField(null=True)      # B站用户ID
    sessdata = models.TextField(null=True)              # B站SESSDATA
    bili_jct = models.CharField(max_length=50, null=True)
    refresh_token = models.CharField(max_length=100, null=True)
    access_token = models.CharField(max_length=100, null=True)
    # 过滤与去重配置（同 UserConfig，下略）
    min_length = models.IntegerField(default=1)
    max_length = models.IntegerField(default=500)
    dedup_method = models.CharField(max_length=20, default='exact')
    background_color = models.CharField(max_length=7, default='#1a1a2e')
    opacity = models.FloatField(default=0.95)
```

##### 5.3.7 用户视频历史表 (user_video_history)

```python
class UserVideoHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    analyzed_at = models.DateTimeField(auto_now=True)
    is_favorite = models.BooleanField(default=False)
    note = models.CharField(max_length=255, null=True)
    # unique_together = ['user', 'video']
```

##### 5.3.8 用户配置表 (user_config)

```python
class UserConfig(models.Model):
    id = models.BigIntegerField(primary_key=True)   # 单例，pk=1
    # 过滤、去重、白名单、UI配置字段（同 User，参见 users 表
    min_length = models.IntegerField(default=1)
    max_length = models.IntegerField(default=500)
    dedup_method = models.CharField(max_length=20, default='exact')
    # ...
    updated_at = models.DateTimeField(auto_now=True)
    @classmethod
    def get_config(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config
```

##### 5.3.9 邮箱验证码表 (email_verification_codes)

```python
class EmailVerificationCode(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, default='register')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
```

---

## 6. API接口文档

### 6.1 情感分析接口

#### 6.1.1 同步分析接口

```
POST /api/analyze/{bv_id}
```

**请求参数**：
```json
{
    "videoBvid": "BV1xx411x7x1"
}
```

**响应格式**：
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

#### 6.1.2 异步分析接口

```
POST /api/video/async-analyze/
```

**请求参数**：
```json
{
    "bvid": "BV1xx411x7x1"
}
```

**响应格式**：
```json
{
    "success": true,
    "task_id": "abc123",
    "status": "pending"
}
```

#### 6.1.3 任务状态查询

```
GET /api/task/status/{task_id}/
```

**响应格式**：
```json
{
    "task_id": "abc123",
    "status": "SUCCESS",
    "result": {
        "positive_count": 234,
        "neutral_count": 123,
        "negative_count": 45
    }
}
```

### 6.2 视频信息接口

```
GET /api/video/info/{bvid}/
```

**响应格式**：
```json
{
    "success": true,
    "data": {
        "bvid": "BV1xx411x7x1",
        "title": "视频标题",
        "author": "UP主",
        "pubdate": "2024-01-01T12:00:00Z",
        "view": 123456,
        "like": 5678,
        "coin": 1234,
        "favorite": 2345,
        "share": 345
    }
}
```

### 6.3 评论数据接口

```
GET /api/video/comments/{bvid}/
```

**响应格式**：
```json
{
    "success": true,
    "data": {
        "comments": [
            {
                "rpid": 123456789,
                "message": "评论内容",
                "uname": "用户名",
                "sentiment_score": 0.85,
                "sentiment_label": "positive",
                "like_count": 100
            }
        ],
        "total_count": 402,
        "page": 1,
        "page_size": 20
    }
}
```

---

## 7. 关键技术实现

### 7.1 API请求认证机制

> **重要说明**：B站API采用多种安全机制保护接口，本项目仅介绍通用的API认证概念。实际使用时请务必遵守B站《用户协议》和《开发者协议》，并优先使用B站官方提供的SDK和接口。

#### 7.1.1 认证机制概述

B站API接口采用多种认证方式来确保请求的安全性和合法性：

| 认证方式 | 说明 | 适用场景 |
|---------|------|---------|
| Cookie认证 | 通过登录后的Cookie进行身份验证 | 需要登录用户操作 |
| SESSDATA | 登录会话凭证，有效期约一个月 | 大部分API调用 |
| Access Token | OAuth2.0访问令牌 | 第三方应用授权 |
| WBI签名 | 请求参数签名防篡改 | 部分敏感API |

#### 7.1.2 认证凭证获取

```python
# 通过登录获取SESSDATA
# 建议使用B站官方APP扫码登录获取凭证
def get_sessdata():
    # 方式一：通过浏览器开发者工具查看B站请求头
    # 方式二：使用B站官方开放平台SDK
    # 方式三：遵守的前提下B站协议自行实现登录逻辑
    pass
```

**获取凭证的建议方式**：

1. **官方渠道**：使用B站开放平台官方SDK
2. **浏览器登录**：在浏览器登录后从开发者工具复制Cookie
3. **扫码登录**：通过B站APP扫码获取临时凭证

> ⚠️ **合规提示**：请勿使用自动化工具批量注册账号或模拟登录，这可能违反B站服务条款。建议控制请求频率，尊重平台资源。

#### 7.1.3 请求头配置

```python
# 基础请求头配置
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.bilibili.com',
    'Accept': 'application/json, text/plain, */*',
    # 登录凭证
    'Cookie': f'SESSDATA={sessdata}'
}
```

#### 7.1.4 频率控制与礼貌爬取

为保证服务稳定性和遵守平台规则，请务必实施以下措施：

1. **请求频率限制**
   - 每秒不超过1次请求
   - 批量操作时设置合理间隔

2. **合理设置请求头**
   - 使用标准User-Agent
   - 携带Referer来源
   - 保持Cookie有效

3. **错误处理与重试**
   - 遇到限流(429)时 exponential backoff
   - 账号异常时停止请求并检查

4. **数据使用规范**
   - 仅用于个人学习研究
   - 不进行商业盈利
   - 尊重用户隐私，不存储个人信息

### 7.2 代理池实现

```cpp
class ProxyPool {
    std::vector<std::string> exclusive_proxies_;   // 独享代理
    std::vector<std::string> short_proxies_;       // 短效代理

    // 自动切换策略
    std::string get_next_proxy() {
        if (!exclusive_proxies_.empty()) {
            return exclusive_proxies_.front();
        }
        // 动态获取短效代理
        return fetch_short_proxy();
    }
};
```

### 7.3 数据清洗流程

系统实现了四阶段数据清洗：

1. **阶段一：文本清洗**
   - 繁简转换
   - 特殊字符过滤
   - HTML标签去除

2. **阶段二：垃圾检测**
   - 重复字符检测
   - 垃圾文本识别
   - 低质量评论过滤

3. **阶段三：语义去重**
   - 精确去重（完全相同）
   - 模糊去重（相似度>85%）
   - 语义去重（Embedding相似度>85%）

4. **阶段四：质量评分**
   - 多维度质量评估
   - 综合质量分数计算

### 7.4 SSE实时推送

```python
# 使用Django流式响应实现SSE
def sse_progress(request, task_id):
    def event_stream():
        # 监听Redis消息
        pubsub = redis_client.pubsub()
        pubsub.subscribe(f'task_progress:{task_id}')
        for message in pubsub.listen():
            if message['type'] == 'message':
                yield f"data: {message['data']}\n\n"
    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')
```

### 7.5 WebSocket通信

```javascript
// Electron WebSocket服务端
const wss = new WebSocket.Server({ port: 3000 });

wss.on('connection', (ws) => {
    // 处理Chrome扩展连接
    ws.on('message', (message) => {
        const data = JSON.parse(message);
        if (data.type === 'VIDEO_CHANGE') {
            // 触发后端分析
            analyzeVideo(data.bvId);
        }
    });
});
```

---

### 7.6 Redis缓存与消息队列

Redis在本系统中承担着缓存服务、消息队列、实时数据存储三大核心角色，是整个系统高性能运行的关键组件。

#### 7.6.1 Redis架构设计

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Redis 集群架构                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐           │
│   │   Master    │────│   Slave 1   │────│   Slave 2   │           │
│   │  (写入/读取)  │    │  (只读)     │    │  (只读)     │           │
│   └─────────────┘    └─────────────┘    └─────────────┘           │
│                                                                     │
│   持久化策略：RDB + AOF                                             │
│   内存策略：volatile-lru                                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Redis部署配置**：

| 配置项 | 值 | 说明 |
|-------|-----|-----|
| 持久化 | RDB + AOF | 双重保障 |
| RDB触发 | 60秒1次 | 最多1000个key变化 |
| AOF策略 | everysec | 每秒同步 |
| 内存限制 | 4GB | 根据数据量调整 |
| 过期策略 | volatile-lru | 优先淘汰过期键 |
| 连接池 | 50连接 | 高并发支持 |

#### 7.6.2 Redis数据结构设计

本系统使用多种Redis数据结构来满足不同业务需求：

**1. String - 简单缓存**

```python
# 视频分析结果缓存
# Key: video:sentiment:{bvid}
# Value: JSON序列化结果
# TTL: 24小时

def cache_sentiment_result(bvid, result):
    key = f"video:sentiment:{bvid}"
    redis_client.setex(
        key,
        86400,  # 24小时
        json.dumps(result)
    )

def get_cached_result(bvid):
    key = f"video:sentiment:{bvid}"
    data = redis_client.get(key)
    return json.loads(data) if data else None
```

**2. Hash - 视频详细信息**

```python
# 视频信息缓存
# Key: video:info:{bvid}
# Field: title, author, view, like, coin, favorite, ...

def cache_video_info(bvid, info_dict):
    key = f"video:info:{bvid}"
    redis_client.hset(key, mapping=info_dict)
    redis_client.expire(key, 3600)  # 1小时过期

def get_video_info(bvid):
    key = f"video:info:{bvid}"
    return redis_client.hgetall(key)
```

**3. List - 任务队列**

```python
# Celery任务队列
# Key: celery:tasks
# Value: 任务JSON列表

def push_task(task_data):
    redis_client.lpush('celery:tasks', json.dumps(task_data))

def pop_task():
    task_json = redis_client.brpop('celery:tasks', timeout=5)
    return json.loads(task_json[1]) if task_json else None
```

**4. Sorted Set - 热度排行榜**

```python
# 视频热度排行
# Key: video:rankings
# Score: 综合热度分数
# Member: bvid

def update_video_rank(bvid, score):
    redis_client.zadd('video:rankings', {bvid: score})

def get_top_videos(limit=10):
    return redis_client.zrevrange('video:rankings', 0, limit - 1, withscores=True)
```

**5. Set - 用户会话管理**

```python
# 在线用户集合
# Key: online:users
# Member: user_id

def user_login(user_id):
    redis_client.sadd('online:users', user_id)

def user_logout(user_id):
    redis_client.srem('online:users', user_id)

def get_online_count():
    return redis_client.scard('online:users')
```

**6. Pub/Sub - 实时消息推送**

```python
# 任务进度推送
# Channel: task:progress:{task_id}
# Message: JSON进度数据

def publish_progress(task_id, progress_data):
    channel = f"task:progress:{task_id}"
    redis_client.publish(channel, json.dumps(progress_data))

def subscribe_progress(task_id):
    pubsub = redis_client.pubsub()
    pubsub.subscribe(f"task:progress:{task_id}")
    return pubsub
```

#### 7.6.3 缓存策略实现

```python
class CacheStrategy:
    """缓存策略管理器"""

    # 缓存键前缀
    PREFIX_VIDEO_SENTIMENT = "video:sentiment:"
    PREFIX_VIDEO_INFO = "video:info:"
    PREFIX_USER_SESSION = "user:session:"
    PREFIX_API_RESPONSE = "api:response:"

    # 缓存过期时间(秒)
    TTL_SENTIMENT = 86400      # 24小时 - 视频情感分析结果
    TTL_VIDEO_INFO = 3600      # 1小时 - 视频基本信息
    TTL_USER_SESSION = 604800   # 7天 - 用户会话
    TTL_API_RESPONSE = 300      # 5分钟 - API响应缓存
    TTL_PROXY_POOL = 300       # 5分钟 - 代理池状态

    def __init__(self, redis_client):
        self.redis = redis_client

    def get_or_set(self, key, fetch_func, ttl):
        """缓存读取模式：先获取，缺失时设置"""
        # 尝试从缓存获取
        cached = self.redis.get(key)
        if cached:
            return json.loads(cached)

        # 缓存未命中，从数据源获取
        data = fetch_func()

        # 存入缓存
        if data:
            self.redis.setex(key, ttl, json.dumps(data))

        return data

    def invalidate_pattern(self, pattern):
        """批量失效缓存"""
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)

    def cache_with_version(self, key, data, ttl, version):
        """带版本号的缓存"""
        versioned_key = f"{key}:v{version}"
        self.redis.setex(versioned_key, ttl, json.dumps(data))
        # 更新版本号
        self.redis.set(f"{key}:version", version)
```

#### 7.6.4 分布式锁实现

使用Redis实现分布式锁，保证多进程/多机器环境下的数据一致性：

```python
import redis
import time
import uuid

class DistributedLock:
    """Redis分布式锁"""

    def __init__(self, redis_client, lock_name, expire_time=30):
        self.redis = redis_client
        self.lock_name = f"lock:{lock_name}"
        self.expire_time = expire_time
        self.lock_value = str(uuid.uuid4())
        self.acquired = False

    def acquire(self, timeout=10):
        """获取锁"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            # SET NX + EX 原子操作
            acquired = self.redis.set(
                self.lock_name,
                self.lock_value,
                nx=True,  # 仅当key不存在时设置
                ex=self.expire_time  # 过期时间
            )
            if acquired:
                self.acquired = True
                return True
            time.sleep(0.01)  # 10ms重试间隔
        return False

    def release(self):
        """释放锁"""
        if not self.acquired:
            return False
        # 使用Lua脚本确保原子性释放
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        self.redis.eval(lua_script, 1, self.lock_name, self.lock_value)
        self.acquired = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
```

#### 7.6.5 消息队列设计

```python
class MessageQueue:
    """Redis消息队列管理器"""

    # 队列名称
    QUEUE_CRAWL = "queue:crawl"
    QUEUE_ANALYZE = "queue:analyze"
    QUEUE_NOTIFY = "queue:notify"

    # 优先级
    PRIORITY_HIGH = 1
    PRIORITY_NORMAL = 2
    PRIORITY_LOW = 3

    def __init__(self, redis_client):
        self.redis = redis_client

    def enqueue(self, queue_name, message, priority=PRIORITY_NORMAL):
        """入队"""
        # 使用Sorted Set实现优先级队列
        score = priority
        self.redis.zadd(queue_name, {json.dumps(message): score})

    def dequeue(self, queue_name, timeout=0):
        """出队"""
        if timeout > 0:
            # 阻塞出队
            result = self.redis.zpopmin(queue_name, 1)
            if result:
                return json.loads(result[0][0])
            return None
        else:
            # 立即出队
            result = self.redis.zpopmin(queue_name)
            if result:
                return json.loads(result[0][0])
            return None

    def get_queue_length(self, queue_name):
        """获取队列长度"""
        return self.redis.zcard(queue_name)
```

#### 7.6.6 性能优化技巧

1. **Pipeline批量操作**
```python
# 批量获取多个缓存
def batch_get_cached(bvid_list):
    pipeline = redis_client.pipeline()
    for bvid in bvid_list:
        pipeline.get(f"video:sentiment:{bvid}")
    return pipeline.execute()
```

2. **Lua脚本原子操作**
```python
# 原子计数器
lua_incr = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""
redis_client.eval(lua_incr, 1, "video:view:count", 3600)
```

3. **Redis集群水平扩展**
```python
# 使用Redis Cluster实现数据分片
# 槽位范围: 0-16383
# 自动故障转移
```

---

## 8. 性能优化策略

### 8.1 缓存策略

| 缓存类型 | 存储介质 | 过期时间 | 用途 |
|---------|---------|---------|------|
| 视频分析结果 | Redis | 24小时 | 避免重复分析 |
| 用户配置 | Redis | 永久 | 快速读取 |
| API响应 | Redis | 5分钟 | 热点数据加速 |

### 8.2 异步处理

```python
# Celery任务配置
@celery_app.task(bind=True, max_retries=3)
def crawl_and_analyze_comments(self, bvid, cookie):
    try:
        # 分批处理，每批1000条
        for page in range(0, total_pages, batch_size):
            # 爬取数据
            # 更新进度
            self.update_state(state='PROGRESS', meta={
                'progress': (page / total_pages) * 100
            })
    except Exception as e:
        # 失败重试
        self.retry(exc=e, countdown=60)
```

### 8.3 连接复用

- HTTP连接池：requests.Session()复用TCP连接
- 数据库连接：Django连接池
- Redis连接：连接池管理

### 8.4 内存管理

- 批量处理：防止OOM
- 及时释放：使用完模型后清理
- 垃圾回收：定期触发GC

---

## 9. 部署方案

### 9.1 生产环境部署架构

```
                    ┌─────────────────┐
                    │   用户浏览器     │
                    └────────┬────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│                         Nginx (80/443)                       │
│                    反向代理 + 负载均衡                         │
└────────────────────────────┬────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Django (8000) │    │ Django (8001) │    │ Django (8002) │
│  Gunicorn     │    │  Gunicorn     │    │  Gunicorn     │
└───────┬───────┘    └───────┬───────┘    └───────┬───────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ MySQL 主库    │    │    Redis      │    │  C++ 爬虫服务 │
│   (3306)      │    │   (6379)      │    │    (8080)     │
└───────────────┘    └───────────────┘    └───────────────┘
```

### 9.2 Supervisor配置

```ini
[program:bilibili_celery]
command=/root/bilibili_analysis/venv/bin/celery -A bilibili_analysis worker -c 4 -l info
directory=/root/bilibili_analysis
user=root
autostart=true
autorestart=true
stdout_logfile=/var/log/celery.log

[program:bilibili_gunicorn]
command=/root/bilibili_analysis/venv/bin/gunicorn --config gunicorn_config.py bilibili_analysis.wsgi:application
directory=/root/bilibili_analysis
user=root
autostart=true
autorestart=true
```

### 9.3 Nginx配置

```nginx
upstream bilibili_app {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://bilibili_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias /root/bilibili_analysis/static/;
    }
}
```

---

## 10. 使用指南

### 10.1 环境要求

| 环境 | 要求 |
|-----|-----|
| Python | 3.10+ |
| Node.js | 16+ |
| C++编译器 | GCC 9+ |
| MySQL | 8.0+ |
| Redis | 7.0+ |
| Chrome | 最新版 |

### 10.2 快速启动

#### 后端启动

```bash
cd /root/bilibili_analysis

# 激活虚拟环境
source venv/bin/activate

# 启动Redis
redis-server

# 启动Celery (4个worker)
celery -A bilibili_analysis worker -c 4 -l info

# 数据库迁移
python manage.py makemigrations
python manage.py migrate

# 启动Django
python manage.py runserver 0.0.0.0:8000
```

#### 爬虫服务启动

```bash
cd crawler_service
mkdir -p build && cd build
cmake ..
make
./crawler_service
```

#### Electron启动

```bash
cd electron
npm install
npm start
```

#### Chrome扩展安装

1. 打开 `chrome://extensions/`
2. 开启"开发者模式"
3. 加载 `chrome_extension` 文件夹

### 10.3 使用流程

1. **启动Django后端服务**
2. **启动Electron悬浮窗口**
3. **安装并启用Chrome扩展**
4. **访问B站视频页面**
5. **系统自动分析并展示结果**

---

## 附录

### 项目目录结构

```
bilibili_analysis/
├── bilibili_analysis/          # Django项目主目录
├── analysis/                   # Django应用
│   ├── models.py              # 数据模型
│   ├── views.py              # API视图
│   ├── services.py           # 业务逻辑
│   ├── tasks.py              # Celery任务
│   ├── sentiment_model.py   # 文本情感模型
│   ├── audio_sentiment_model.py  # 音频情感模型
│   └── multimodal_attention.py  # 多模态融合
├── crawler_service/           # C++爬虫服务
│   ├── src/
│   │   ├── crawler.cpp       # 爬虫实现
│   │   ├── crawler.h
│   │   ├── wbi_signer.h      # WBI签名
│   │   └── main.cpp
│   └── CMakeLists.txt
├── electron/                  # Electron悬浮窗口
│   ├── main.js              # 主进程
│   ├── src/
│   │   ├── index.html       # 主界面
│   │   ├── emotional-analysis.html
│   │   ├── video-audio-analysis.html
│   │   └── user-profile.html
│   └── package.json
├── chrome_extension/          # Chrome扩展
│   ├── manifest.json
│   ├── content.js
│   └── background.js
├── models/                    # AI模型
│   ├── text_sentiment/       # 文本情感模型
│   └── audio_emotion/        # 音频情感模型
├── requirements.txt
└── manage.py
```

### 技术文档版本

- 版本：1.0.0
- 更新日期：2026年3月4日
- 作者：B站视频情感分析系统开发团队
