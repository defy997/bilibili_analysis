// B站视频情感分析助手 - 后台脚本
// 处理扩展的生命周期和一些全局功能

console.log('🎬 B站情感分析助手后台服务已启动');

// 扩展安装时的处理
chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === 'install') {
        console.log('✅ 扩展已安装');

        // 显示欢迎页面或设置页面
        chrome.tabs.create({
            url: chrome.runtime.getURL('welcome.html')
        });

    } else if (details.reason === 'update') {
        console.log('🔄 扩展已更新到版本', chrome.runtime.getManifest().version);
    }
});

// 处理扩展图标点击
chrome.action.onClicked.addListener((tab) => {
    // 检查是否在B站视频页面
    if (tab.url && tab.url.includes('bilibili.com/video/')) {
        // 在当前标签页中执行content script（如果还没有执行的话）
        chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content.js']
        });
    } else {
        // 显示提示信息
        chrome.tabs.create({
            url: 'https://www.bilibili.com'
        });
    }
});

// 监听来自content script的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log('📨 收到来自content script的消息:', message);

    // 处理不同的消息类型
    switch (message.type) {
        case 'VIDEO_DETECTED':
            // 视频检测成功
            console.log('🎥 检测到视频:', message.bvId);
            break;

        case 'ANALYSIS_REQUEST':
            // 转发分析请求（如果需要的话）
            break;
        case 'VIDEO_CHANGE':
            console.log('🔔 收到 VIDEO_CHANGE，BV:', message.bvId);
            // 转发或处理视频变化逻辑（不再读取 SESSDATA）
            break;

        default:
            console.log('📨 收到未知类型的消息:', message);
    }

    // 发送响应
    sendResponse({ received: true });
});

// 定期检查扩展状态
setInterval(() => {
    // 检查WebSocket连接状态等
    console.log('🔍 扩展状态检查...');
}, 30000); // 每30秒检查一次

// 处理扩展卸载
chrome.runtime.setUninstallURL('https://github.com/your-repo/bilibili-sentiment-analysis');

// 导出一些工具函数
const utils = {
    // 验证BV号格式
    isValidBvId: (bvId) => {
        return /^BV[a-zA-Z0-9]{10}$/.test(bvId);
    },

    // 从URL提取BV号
    extractBvId: (url) => {
        const match = url.match(/video\/(BV[a-zA-Z0-9]+)/);
        return match ? match[1] : null;
    },

    // 获取当前时间戳
    getTimestamp: () => {
        return Date.now();
    }
};

// 使工具函数在全局范围内可用
globalThis.extensionUtils = utils;
