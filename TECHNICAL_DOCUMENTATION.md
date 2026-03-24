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

### 5.1 核心数据表

#### 5.1.1 视频表 (videos)

```python
class Video(models.Model):
    bvid = models.CharField(max_length=20, primary_key=True)  # BV号
    aid = models.BigIntegerField(unique=True)  # AV号
    cid = models.BigIntegerField(null=True)  # 弹幕CID
    title = models.CharField(max_length=255, null=True)  # 标题
    pubdate = models.DateTimeField(null=True)  # 发布日期

    # 视频统计数据
    view = models.BigIntegerField(default=0)  # 播放量
    like = models.BigIntegerField(default=0)  # 点赞数
    coin = models.BigIntegerField(default=0)  # 投币数
    favorite = models.BigIntegerField(default=0)  # 收藏数
    share = models.BigIntegerField(default=0)  # 分享数

    raw_comment_count = models.IntegerField(default=0)  # 原始评论数
```

#### 5.1.2 评论表 (comments)

```python
class Comment(models.Model):
    rpid = models.BigIntegerField(primary_key=True)  # 评论ID
    video = models.ForeignKey(Video, on_delete=models.CASCADE)  # 关联视频

    # 用户信息
    mid = models.BigIntegerField(db_index=True)  # 用户UID
    uname = models.CharField(max_length=100, null=True)  # 用户名

    # 评论内容
    message = models.TextField()  # 评论正文
    like_count = models.IntegerField(default=0)  # 点赞数
    reply_count = models.IntegerField(default=0)  # 回复数
    location = models.CharField(max_length=50, null=True)  # IP属地
    ctime = models.DateTimeField(null=True)  # 发布时间

    # 用户属性
    vip_type = models.IntegerField(default=0)  # 会员类型
    user_level = models.IntegerField(default=0)  # 用户等级

    # 情感分析
    sentiment_score = models.FloatField(default=0.5)  # 情感得分(0-1)
    sentiment_label = models.CharField(max_length=10, default="neutral")  # 情感标签

    # 数据清洗
    quality_score = models.FloatField(default=0.5)  # 质量评分
    is_duplicate = models.BooleanField(default=False)  # 是否重复
```

#### 5.1.3 弹幕表 (danmus)

```python
class Danmu(models.Model):
    cid = models.BigIntegerField(db_index=True)  # 关联视频CID
    video_time = models.FloatField(default=0)  # 视频内出现时间
    content = models.TextField()  # 弹幕内容
    send_time = models.DateTimeField(null=True)  # 发送时间
    user_hash = models.CharField(max_length=20, null=True)  # 发送者Hash

    # 情感分析
    sentiment_score = models.FloatField(default=0.5)
    sentiment_label = models.CharField(max_length=10, default="neutral")

    # 数据清洗
    quality_score = models.FloatField(default=0.5)
    is_duplicate = models.BooleanField(default=False)
```

#### 5.1.4 音频情感表 (audio_sentiments)

```python
class AudioSentiment(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    time_offset = models.FloatField()  # 视频时间偏移(秒)
    sentiment_score = models.FloatField(default=0.5)
    sentiment_label = models.CharField(max_length=10, default="neutral")
    emotion_probs = models.JSONField(default=dict)  # 各情感概率分布
    segment_duration = models.FloatField(default=15)  # 分段时长
    text_transcript = models.TextField(null=True)  # ASR转录文本
```

#### 5.1.5 多模态融合表 (multimodal_sentiments)

```python
class MultimodalSentiment(models.Model):
    video = models.OneToOneField(Video, on_delete=models.CASCADE)

    # 融合后的三分类结果
    fused_positive = models.FloatField(default=0.33)
    fused_neutral = models.FloatField(default=0.33)
    fused_negative = models.FloatField(default=0.34)

    # 各模态注意力权重
    audio_weight = models.FloatField(default=0.35)
    text_weight = models.FloatField(default=0.35)
    danmu_weight = models.FloatField(default=0.30)

    # 各模态原始情感分布
    audio_emotion = models.JSONField(default=dict)
    text_emotion = models.JSONField(default=dict)
    danmu_emotion = models.JSONField(default=dict)

    # 冲突检测
    has_conflict = models.BooleanField(default=False)
    conflict_details = models.JSONField(default=dict)

    # 元数据
    video_type = models.CharField(max_length=20, default='general')
    dominant_emotion = models.CharField(max_length=20, default='neutral')
    emotion_strength = models.FloatField(default=0.0)
    overall_score = models.FloatField(default=0.5)
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
