// B站视频情感分析助手 - 内容脚本
// 负责监控B站页面的视频变化，并通过WebSocket通知悬浮窗口

class BilibiliVideoMonitor {
    constructor() {
        this.socket = null;
        this.lastBvId = null;
        this.reconnectAttempts = 0;
        this.reconnectDelay = 2000; // 初始重连间隔 2秒

        this.init();
    }

    init() {
        console.log('🎬 B站视频监控器已启动');

        // 连接到悬浮窗口的WebSocket服务器
        this.connectWebSocket();

        // 开始监控视频变化
        this.startMonitoring();

        // 页面卸载时清理资源
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });
    }

    connectWebSocket() {
        try {
            this.socket = new WebSocket('ws://localhost:3000');

            this.socket.onopen = () => {
                console.log('✅ 已连接到悬浮窗口');
                this.reconnectAttempts = 0;

                // 发送连接成功消息
                this.sendMessage({
                    type: 'EXTENSION_CONNECTED',
                    timestamp: Date.now()
                });

                // 连接成功后，立即发送当前视频信息
                const currentBvId = this.extractBvId(window.location.href);
                if (currentBvId) {
                    this.lastBvId = currentBvId;
                    this.notifyVideoChange(currentBvId);
                }
            };

            this.socket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    console.log('📨 收到悬浮窗口消息:', message);

                    // 处理来自悬浮窗口的消息
                    this.handleMessage(message);
                } catch (error) {
                    console.error('❌ 解析WebSocket消息失败:', error);
                }
            };

            this.socket.onclose = () => {
                console.log('🔌 与悬浮窗口的连接已断开');
                this.handleReconnect();
            };

            this.socket.onerror = (error) => {
                console.error('🚨 WebSocket连接错误:', error);
            };

        } catch (error) {
            console.error('🚨 创建WebSocket连接失败:', error);
            this.handleReconnect();
        }
    }

    handleReconnect() {
        this.reconnectAttempts++;
        // 指数退避：2s → 4s → 8s → 16s，最长 30s，然后一直以 30s 间隔重试
        const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000);
        console.log(`🔄 ${delay / 1000}s后尝试重连 (第${this.reconnectAttempts}次)`);

        setTimeout(() => {
            this.connectWebSocket();
        }, delay);
    }

    startMonitoring() {
        // 立即检查当前视频
        this.checkVideoChange();

        // 设置定时器，每2秒检查一次视频变化
        this.monitorInterval = setInterval(() => {
            this.checkVideoChange();
        }, 2000);

        console.log('👀 开始监控视频变化...');
    }

    checkVideoChange() {
        try {
            // 从URL中提取BV号
            const currentBvId = this.extractBvId(window.location.href);

            if (currentBvId && currentBvId !== this.lastBvId) {
                console.log(`🎥 检测到视频变化: ${this.lastBvId} → ${currentBvId}`);
                this.lastBvId = currentBvId;

                // 通知悬浮窗口
                this.notifyVideoChange(currentBvId);
            }
        } catch (error) {
            console.error('❌ 检查视频变化时出错:', error);
        }
    }

    extractBvId(url) {
        // 匹配B站视频URL中的BV号
        const patterns = [
            /video\/(BV[a-zA-Z0-9]+)/,  // 标准视频页面
            /BV([a-zA-Z0-9]+)/,         // 其他页面中的BV号
        ];

        for (const pattern of patterns) {
            const match = url.match(pattern);
            if (match && match[1]) {
                return match[1];
            }
        }

        return null;
    }

    notifyVideoChange(bvId) {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            console.warn('⚠️ WebSocket未连接，无法发送视频变化通知');
            return;
        }

        const message = {
            type: 'VIDEO_CHANGE',
            bvId: bvId,
            url: window.location.href,
            timestamp: Date.now(),
            title: this.getVideoTitle()
        };

        this.sendMessage(message);
        console.log('📤 已发送视频变化通知:', message);
    }

    getVideoTitle() {
        try {
            // 尝试获取视频标题
            const titleElement = document.querySelector('h1.video-title, .video-info-title, [data-title]');
            if (titleElement) {
                return titleElement.textContent.trim();
            }

            // 从document.title中提取
            const titleMatch = document.title.match(/^(.+?)_哔哩哔哩_bilibili$/);
            if (titleMatch) {
                return titleMatch[1];
            }

            return '未知视频标题';
        } catch (error) {
            console.error('❌ 获取视频标题失败:', error);
            return '未知视频标题';
        }
    }

    sendMessage(message) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(message));
        }
    }

    handleMessage(message) {
        // 处理来自悬浮窗口的消息
        switch (message.type) {
            case 'PING':
                // 响应心跳包
                this.sendMessage({ type: 'PONG', timestamp: Date.now() });
                break;

            case 'REQUEST_CURRENT_VIDEO':
                // 重新发送当前视频信息
                if (this.lastBvId) {
                    this.notifyVideoChange(this.lastBvId);
                }
                break;

            default:
                console.log('📨 收到未知类型的消息:', message);
        }
    }

    cleanup() {
        console.log('🧹 清理B站视频监控器资源');

        // 清除定时器
        if (this.monitorInterval) {
            clearInterval(this.monitorInterval);
        }

        // 关闭WebSocket连接
        if (this.socket) {
            this.socket.close();
        }
    }
}

// 页面加载完成后启动监控器
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        new BilibiliVideoMonitor();
    });
} else {
    new BilibiliVideoMonitor();
}

// 导出给其他脚本使用
window.BilibiliVideoMonitor = BilibiliVideoMonitor;
