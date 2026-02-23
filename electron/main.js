const { app, BrowserWindow, ipcMain, screen, Tray, Menu, nativeImage, session } = require('electron');
app.isQuitting = false;
const path = require('path');
const WebSocket = require('ws');
const http = require('http');

// 配置 session 以支持跨域 Cookie
// 使用默认 session
app.on('ready', () => {
    console.log('✅ Electron session 配置完成');
});

// HTTP 服务器用于接收 Django 后端的任务完成通知
let httpServer;

// 创建 HTTP 服务器用于接收任务通知
function createNotificationServer() {
    httpServer = http.createServer((req, res) => {
        // 设置 CORS 头
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

        if (req.method === 'OPTIONS') {
            res.writeHead(200);
            res.end();
            return;
        }

        if (req.method === 'POST' && req.url === '/api/task-notify/') {
            let body = '';
            req.on('data', chunk => {
                body += chunk.toString();
            });
            req.on('end', () => {
                try {
                    const data = JSON.parse(body);
                    console.log('[TaskNotify] 收到任务完成通知:', data);

                    // 广播任务完成消息到所有窗口
                    broadcastTaskComplete(data);

                    res.writeHead(200, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ success: true }));
                } catch (error) {
                    console.error('[TaskNotify] 解析通知失败:', error);
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'Invalid JSON' }));
                }
            });
        } else {
            res.writeHead(404);
            res.end();
        }
    });

    httpServer.listen(3001, () => {
        console.log('✅ 任务通知服务器启动在端口 3001');
    });
}

// 广播任务完成消息到所有窗口
function broadcastTaskComplete(data) {
    const windows = [
        mainWindow, analysisWindow, userProfileWindow,
        videoAudioWindow, overallReportsWindow, expandedWindow
    ];
    windows.forEach(win => {
        if (win && !win.isDestroyed()) {
            win.webContents.send('task-complete', data);
        }
    });
}

// 设置控制台输出编码为UTF-8(解决Windows终端中文乱码)
if (process.platform === 'win32') {
  process.stdout.setDefaultEncoding('utf-8');
  process.stderr.setDefaultEncoding('utf-8');
}

// 保持对window对象的全局引用
let mainWindow;
let analysisWindow; // 情感分析窗口
let userProfileWindow; // 用户画像窗口
let videoAudioWindow; // 视频音频分析窗口
let overallReportsWindow; // 多模态情感分析报告窗口
let expandedWindow; // 展开仪表盘窗口
let bilibiliLoginWindow; // B站扫码登录窗口
let wss; // WebSocket服务器，用于与Chrome插件通信
let tray = null; // 系统托盘
let lastWindowPosition = null; // 记录上次主窗口位置以便还原
let currentBvId = null; // 当前正在观看的视频BV号
let currentVideoTitle = null; // 当前视频标题
let analysisMode = 'online'; // 当前分析模式: 'online' (在线) 或 'history' (历史)

function createWindow() {
  // 获取屏幕工作区和鼠标位置，用于定位悬浮窗口（默认靠近当前鼠标/活动窗口）
  const workArea = screen.getPrimaryDisplay().workArea;
  const { width, height, x: workX, y: workY } = workArea;
  const cursorPoint = screen.getCursorScreenPoint();

  // 计算默认位置：鼠标右下方（向左/向上偏移），并确保不超出屏幕工作区
  const defaultWidth = 600;
  const defaultHeight = 712;
  let defaultX = cursorPoint.x - Math.floor(defaultWidth / 2);
  let defaultY = cursorPoint.y - Math.floor(defaultHeight / 2);

  // 如果上次有保存的位置，优先使用（还原）
  if (lastWindowPosition && lastWindowPosition.x !== undefined) {
    defaultX = lastWindowPosition.x;
    defaultY = lastWindowPosition.y;
  }

  // 限制在工作区范围内
  defaultX = Math.max(workX, Math.min(defaultX, workX + width - defaultWidth));
  defaultY = Math.max(workY, Math.min(defaultY, workY + height - defaultHeight));

  // 创建浏览器窗口
  mainWindow = new BrowserWindow({
    width: defaultWidth,
    height: defaultHeight,
    x: defaultX,
    y: defaultY,
    frame: false, // 无边框窗口
    alwaysOnTop: true, // 始终置顶
    transparent: true, // 透明背景
    resizable: false, // 禁止调整大小
    skipTaskbar: true, // 不显示在任务栏
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      enableRemoteModule: true,
      webSecurity: false,  // 允许跨域请求
      partition: 'persist:main'  // 使用持久化的 partition 共享 cookie
    },
    // 悬浮窗口样式
    backgroundColor: '#00000000', // 完全透明背景
    hasShadow: false, // 无阴影
    focusable: true,
    show: false // 先隐藏，加载完成后显示
  });

  // 加载应用的index.html
  mainWindow.loadFile('src/index.html');

  // 页面加载完成后显示窗口
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // 当窗口被关闭，这个事件会被触发
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // 记录窗口移动位置，便于下次打开/还原时使用
  mainWindow.on('move', () => {
    try {
      if (mainWindow && !mainWindow.isDestroyed()) {
        const bounds = mainWindow.getBounds();
        lastWindowPosition = { x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height };
      }
    } catch (err) {
      console.error('move handler error:', err);
    }
  });

  // 窗口关闭事件（点击X按钮时隐藏到托盘）
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      console.log('窗口已隐藏到托盘');
    } else {
      console.log('应用正在退出');
    }
  });

  // 设置窗口属性
  mainWindow.setAlwaysOnTop(true, 'floating');
  mainWindow.setVisibleOnAllWorkspaces(true);
  mainWindow.setSkipTaskbar(true);
  mainWindow.setMovable(true);

  // 开发环境下打开开发者工具
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  // 修复：窗口失去焦点后仍然保持置顶（在某些系统/浏览器切换时会被遮挡）
  mainWindow.on('blur', () => {
    try {
      if (mainWindow && !mainWindow.isDestroyed()) {
        // 重申置顶，使用更强的层级尝试覆盖浏览器
        mainWindow.setAlwaysOnTop(true, 'pop-up-menu');
        mainWindow.setVisibleOnAllWorkspaces(true);
      }
    } catch (err) {
      console.error('blur handler error:', err);
    }
  });

  mainWindow.on('focus', () => {
    try {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.setAlwaysOnTop(true, 'pop-up-menu');
        mainWindow.setVisibleOnAllWorkspaces(true);
      }
    } catch (err) {
      console.error('focus handler error:', err);
    }
  });
}

// 创建WebSocket服务器，用于与Chrome插件通信
function createWebSocketServer() {
    wss = new WebSocket.Server({ port: 3000 });

    wss.on('connection', (ws) => {
        console.log('Chrome插件已连接');

        ws.on('message', (data) => {
            try {
                const message = JSON.parse(data);
                console.log('收到消息:', message);

                if (message.type === 'VIDEO_CHANGE') {
                    currentBvId = message.bvId; // 保存当前视频ID
                    currentVideoTitle = message.title || '未知标题';
                    const videoTitle = message.title || '未知标题';
                    console.log('视频切换:', currentBvId, videoTitle);

                    // 构建视频数据
                    const videoData = { bvId: currentBvId, title: videoTitle };

                    // 向主窗口发送信号
                    if (mainWindow && !mainWindow.isDestroyed()) {
                        mainWindow.webContents.send('video-change', videoData);
                        // 通知主窗口刷新历史列表
                        mainWindow.webContents.send('refresh-history');
                    }
                    // 向分析窗口发送信号
                    if (analysisWindow && !analysisWindow.isDestroyed()) {
                        analysisWindow.webContents.send('video-change', videoData);
                    }
                    // 向用户画像窗口发送信号
                    if (userProfileWindow && !userProfileWindow.isDestroyed()) {
                        userProfileWindow.webContents.send('video-change', videoData);
                    }
                    // 向视频音频分析窗口发送信号
                    if (videoAudioWindow && !videoAudioWindow.isDestroyed()) {
                        videoAudioWindow.webContents.send('video-change', videoData);
                    }
                }
            } catch (error) {
                console.error('解析WebSocket消息失败:', error);
            }
        });

        ws.on('close', () => {
            console.log('Chrome插件连接断开');
        });
    });

    console.log('WebSocket服务器启动在端口 3000');
}

// 创建系统托盘
function createTray() {
  // 尝试加载本地图标，如果失败则使用内置图标
  let icon;
  try {
    const iconPath = path.join(__dirname, 'assets', 'tray-icon.png');
    icon = nativeImage.createFromPath(iconPath);

    // 如果图标加载失败或为空，使用默认图标
    if (icon.isEmpty()) {
      throw new Error('Icon file not found');
    }
  } catch (error) {
    // 使用粉色渐变图标（BiliMood 风格 - 粉色渐变圆形 + B站图标）
    icon = nativeImage.createFromDataURL('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAOxAAADsQBlSsOGwAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAAKoSURBVFiF7ZY9TsNAEIW/SYAgAQQ0NDQ0NDQQNNAgKD9AQ0FDQ0FDQ6A/gJpHg6D8AAWF4NdYdpyb1DYPdZzEsq1zf3d2d7GQAObk5H0GdwFwBKC1NscY4wag1lr7OedUKecccs5RliXquqau68g5R1VVEUIIuq4j55w552RZRlVVEUIInHPEGEPOORljUEphjEEphTEGIYSEeZ4nF8cYQ0opcs5RliXquiamaxqGgTEGl8uFtm1RliXquiYlRVmWFEVBt9tF13W0bYuyLBFCoJTCGENKqWQMw8A5R0qJsiwJIRBS4nkeWuvIOUdKipQS5xw550gpxTlHSqniZ4xBa01KqRjGGLTWxJSIKWNd13HO0dQ1KSW01qSUIuccxpjiN8YQ55wYY8g5R1mWhBDIOTN9fX0l5xxt25JSom1bYkq0bUtKibZtSSlRliUhBLTWhBACxhhyzpFzjpxz5Jw755xz8TyPMQZjzPN9X/Hz86uqqoqc87g55yCEgDGGnHPknCORcyalRM45cs6Rc46cc+ScI+ccOefIOUfOOXLOkXOOnHPknCPnHDnnyDlHzjlyzpFzDkIIGGNQSqGUQimFUgqlFEoplFIopVBKoZRCKYVSCqUUSimUUiilUEqhlEIphVIKpRRKKZRSKKVQSn0DfwNXYwF7bC6sTAAAAABJRU5ErkJggg==');
  }

  tray = new Tray(icon);

  console.log('系统托盘创建成功');

  // 托盘菜单
  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示 BiliMood',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    },
    {
      label: '隐藏',
      click: () => {
        if (mainWindow) {
          mainWindow.hide();
        }
      }
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        app.isQuitting = true;

        // 关闭所有窗口
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.destroy();
        }
        if (analysisWindow && !analysisWindow.isDestroyed()) {
          analysisWindow.destroy();
        }
        if (userProfileWindow && !userProfileWindow.isDestroyed()) {
          userProfileWindow.destroy();
        }
        if (videoAudioWindow && !videoAudioWindow.isDestroyed()) {
          videoAudioWindow.destroy();
        }
        if (overallReportsWindow && !overallReportsWindow.isDestroyed()) {
          overallReportsWindow.destroy();
        }
        if (expandedWindow && !expandedWindow.isDestroyed()) {
          expandedWindow.destroy();
        }
        if (bilibiliLoginWindow && !bilibiliLoginWindow.isDestroyed()) {
          bilibiliLoginWindow.destroy();
        }

        // 关闭WebSocket服务器
        if (wss) {
          wss.close();
        }

        // 销毁托盘
        if (tray) {
          tray.destroy();
        }

        // 退出应用
        app.quit();
      }
    }
  ]);

  tray.setToolTip('BiliMood - B站情感分析');
  tray.setContextMenu(contextMenu);

  // 点击托盘图标显示/隐藏窗口
  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
        mainWindow.focus();
      }
    }
  });
}

// Electron 会在初始化后并准备创建浏览器窗口时，调用这个函数
app.whenReady().then(() => {
  // 解决 Electron file:// → http:// 跨域请求不携带 session cookie 的问题
  // 根本原因：Chromium SameSite=Lax 默认策略阻止跨域 POST 请求发送 cookie
  // 用内存变量保存 sessionid，绕过 Electron 对 IP 地址 cookie 存储的限制
  // onBeforeSendHeaders 同步注入，彻底绕过 Chromium SameSite 限制
  const mainSes = session.fromPartition('persist:main');
  let storedSessionId = null;

  // 用单个监听器同时处理登录和登出（Electron 每次调用 onHeadersReceived 会替换上一个监听器）
  mainSes.webRequest.onHeadersReceived(
    { urls: [
        'http://118.25.39.91:8000/api/auth/login/',
        'http://118.25.39.91:8000/api/auth/logout/'
    ]},
    (details, callback) => {
      callback({ responseHeaders: details.responseHeaders });
      if (details.url.includes('/api/auth/login/')) {
        // 登录成功：从 Set-Cookie 提取 sessionid 存入内存
        const setCookieList = details.responseHeaders['set-cookie']
                           || details.responseHeaders['Set-Cookie']
                           || [];
        for (const header of setCookieList) {
          const m = header.match(/sessionid=([^;]+)/i);
          if (m) {
            storedSessionId = m[1];
            console.log('[Cookie] sessionid 已存入内存');
          }
        }
      } else if (details.url.includes('/api/auth/logout/')) {
        // 登出：清除内存中的 sessionid
        storedSessionId = null;
        console.log('[Cookie] 已登出，sessionid 已清除');
      }
    }
  );

  // 对所有 API 请求，同步注入内存中的 sessionid 到 Cookie 头
  mainSes.webRequest.onBeforeSendHeaders(
    { urls: ['http://118.25.39.91:8000/*'] },
    (details, callback) => {
      const requestHeaders = { ...details.requestHeaders };
      if (storedSessionId) {
        requestHeaders['Cookie'] = `sessionid=${storedSessionId}`;
      }
      callback({ requestHeaders });
    }
  );

  createWindow();
  createTray();
  createWebSocketServer();
  createNotificationServer();

  app.on('activate', () => {
    // 在macOS上，当单击dock图标并且没有其他窗口打开时，
    // 通常在应用中重新创建一个窗口
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    } else if (mainWindow) {
      mainWindow.show();
    }
  });
});

// 当全部窗口关闭时退出
app.on('window-all-closed', () => {
  // 在macOS上，除非用户用Cmd + Q确定地退出，
  // 否则绝大部分应用及其菜单栏会保持激活
  if (process.platform !== 'darwin') {
    app.quit();
  }

  // 关闭WebSocket服务器
  if (wss) {
    wss.close();
  }

  // 关闭HTTP通知服务器
  if (httpServer) {
    httpServer.close();
  }
});

// 监听渲染进程的消息
ipcMain.on('minimize-window', () => {
  // 最小化到托盘
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.hide();
  }
});

ipcMain.on('close-window', () => {
  // 直接退出应用
  console.log('收到关闭窗口请求');
  app.isQuitting = true;

  // 关闭所有窗口
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.destroy();
  }
  if (analysisWindow && !analysisWindow.isDestroyed()) {
    analysisWindow.destroy();
  }
  if (userProfileWindow && !userProfileWindow.isDestroyed()) {
    userProfileWindow.destroy();
  }
  if (videoAudioWindow && !videoAudioWindow.isDestroyed()) {
    videoAudioWindow.destroy();
  }
  if (expandedWindow && !expandedWindow.isDestroyed()) {
    expandedWindow.destroy();
  }
  if (bilibiliLoginWindow && !bilibiliLoginWindow.isDestroyed()) {
    bilibiliLoginWindow.destroy();
  }

  // 关闭WebSocket服务器
  if (wss) {
    wss.close();
  }

  // 关闭HTTP通知服务器
  if (httpServer) {
    httpServer.close();
  }

  // 销毁托盘
  if (tray) {
    tray.destroy();
  }

  // 退出应用
  app.quit();
});

ipcMain.on('toggle-window', () => {
  if (mainWindow) {
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
    }
  }
});

ipcMain.on('go-back', () => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.show();
    mainWindow.focus();
  }
});

ipcMain.on('close-module', (event, moduleName) => {
  // 关闭指定模块窗口
  const targetModule = moduleName || 'overall-reports';
  
  if (targetModule === 'analysis' || targetModule === 'emotional') {
    closeAnalysisWindow();
  }
  if (targetModule === 'user-profile' || targetModule === 'user') {
    closeUserProfileWindow();
  }
  if (targetModule === 'video-audio' || targetModule === 'video') {
    closeVideoAudioWindow();
  }
  if (targetModule === 'overall-reports' || targetModule === 'compare') {
    closeOverallReportsWindow();
  }
  
  // 通知主窗口更新状态
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('module-closed', targetModule);
  }
});


// ==========================================
// 分析窗口控制
// ==========================================

// 打开/切换分析窗口
ipcMain.on('toggle-analysis-window', () => {
    if (analysisWindow && !analysisWindow.isDestroyed()) {
        if (analysisWindow.isVisible()) {
            analysisWindow.hide();
        } else {
            analysisWindow.show();
            analysisWindow.focus();
        }
    } else {
        createAnalysisWindow();
    }
});

// 关闭分析窗口
ipcMain.on('close-analysis-window', () => {
    closeAnalysisWindow();
    // 通知主窗口取消激活状态
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('analysis-window-closed');
    }
});

// 打开分析窗口
ipcMain.on('open-analysis-window', () => {
    createAnalysisWindow();
});


// 开发环境下的热重载 (尝试加载)
try {
    require('electron-reloader')(module);
} catch (_) {}

// ==========================================
// 情感分析窗口函数
// ==========================================

// 创建情感分析窗口
function createAnalysisWindow() {
    if (analysisWindow && !analysisWindow.isDestroyed()) {
        analysisWindow.show();
        analysisWindow.focus();
        return;
    }

    const winWidth = 500;
    const winHeight = 600;
    const workArea = screen.getPrimaryDisplay().workArea;

    // 位置在主窗口右边
    let x = 500, y = 300;
    if (lastWindowPosition) {
        x = lastWindowPosition.x + lastWindowPosition.width + 20;
        y = lastWindowPosition.y;
    }

    // 确保窗口在屏幕可见范围内
    x = Math.max(workArea.x, Math.min(x, workArea.x + workArea.width - winWidth));
    y = Math.max(workArea.y, Math.min(y, workArea.y + workArea.height - winHeight));

    analysisWindow = new BrowserWindow({
        width: winWidth,
        height: winHeight,
        x: x,
        y: y,
        frame: false,
        alwaysOnTop: true,
        transparent: true,
        resizable: false,
        skipTaskbar: true,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            enableRemoteModule: true
        },
        backgroundColor: '#00000000',
        hasShadow: false,
        focusable: true,
        show: false
    });

    analysisWindow.loadFile('src/emotional-analysis.html');

    analysisWindow.once('ready-to-show', () => {
        analysisWindow.show();
        analysisWindow.setAlwaysOnTop(true, 'pop-up-menu');
        analysisWindow.setVisibleOnAllWorkspaces(true);
        // 发送当前正在观看的视频ID
        if (currentBvId) {
            analysisWindow.webContents.send('video-change', currentBvId);
        }

        // 开发环境下打开开发者工具
        if (process.env.NODE_ENV === 'development') {
            analysisWindow.webContents.openDevTools({ mode: 'detach' });
        }
    });

    // 兜底：如果 ready-to-show 迟迟不触发，3秒后强制显示并发送视频ID
    setTimeout(() => {
        if (analysisWindow && !analysisWindow.isDestroyed() && !analysisWindow.isVisible()) {
            analysisWindow.show();
            analysisWindow.setAlwaysOnTop(true, 'pop-up-menu');
            // 发送当前正在观看的视频ID
            if (currentBvId) {
                analysisWindow.webContents.send('video-change', currentBvId);
            }
        }
    }, 3000);

    analysisWindow.on('closed', () => {
        analysisWindow = null;
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('analysis-window-closed');
        }
    });

    analysisWindow.on('blur', () => {
        try {
            if (analysisWindow && !analysisWindow.isDestroyed()) {
                analysisWindow.setAlwaysOnTop(true, 'pop-up-menu');
            }
        } catch (err) {
            console.error('blur handler error:', err);
        }
    });
}

// 关闭情感分析窗口
function closeAnalysisWindow() {
    if (analysisWindow && !analysisWindow.isDestroyed()) {
        analysisWindow.hide();
    }
}


// ==========================================
// 用户画像窗口
// ==========================================

// 打开/切换用户画像窗口
ipcMain.on('toggle-user-profile-window', () => {
    if (userProfileWindow && !userProfileWindow.isDestroyed()) {
        if (userProfileWindow.isVisible()) {
            userProfileWindow.hide();
        } else {
            userProfileWindow.show();
            userProfileWindow.focus();
        }
    } else {
        createUserProfileWindow();
    }
});

// 关闭用户画像窗口
ipcMain.on('close-user-profile-window', () => {
    closeUserProfileWindow();
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('user-profile-window-closed');
    }
});

function createUserProfileWindow() {
    if (userProfileWindow && !userProfileWindow.isDestroyed()) {
        userProfileWindow.show();
        userProfileWindow.focus();
        return;
    }

    const winWidth = 500;
    const winHeight = 600;
    const workArea = screen.getPrimaryDisplay().workArea;

    let x = 500, y = 300;
    if (lastWindowPosition) {
        x = lastWindowPosition.x + lastWindowPosition.width + 20;
        y = lastWindowPosition.y;
    }

    // 确保窗口在屏幕可见范围内
    x = Math.max(workArea.x, Math.min(x, workArea.x + workArea.width - winWidth));
    y = Math.max(workArea.y, Math.min(y, workArea.y + workArea.height - winHeight));

    userProfileWindow = new BrowserWindow({
        width: winWidth,
        height: winHeight,
        x: x,
        y: y,
        frame: false,
        alwaysOnTop: true,
        transparent: true,
        resizable: false,
        skipTaskbar: true,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            enableRemoteModule: true
        },
        backgroundColor: '#00000000',
        hasShadow: false,
        focusable: true,
        show: false
    });

    userProfileWindow.loadFile('src/user-profile.html');

    userProfileWindow.once('ready-to-show', () => {
        userProfileWindow.show();
        userProfileWindow.setAlwaysOnTop(true, 'pop-up-menu');
        userProfileWindow.setVisibleOnAllWorkspaces(true);
        // 发送当前正在观看的视频ID
        if (currentBvId) {
            userProfileWindow.webContents.send('video-change', currentBvId);
        }
    });

    // 兜底：如果 ready-to-show 迟迟不触发，3秒后强制显示并发送视频ID
    setTimeout(() => {
        if (userProfileWindow && !userProfileWindow.isDestroyed() && !userProfileWindow.isVisible()) {
            userProfileWindow.show();
            userProfileWindow.setAlwaysOnTop(true, 'pop-up-menu');
            // 发送当前正在观看的视频ID
            if (currentBvId) {
                userProfileWindow.webContents.send('video-change', currentBvId);
            }
        }
    }, 3000);

    userProfileWindow.on('closed', () => {
        userProfileWindow = null;
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('user-profile-window-closed');
        }
    });

    userProfileWindow.on('blur', () => {
        try {
            if (userProfileWindow && !userProfileWindow.isDestroyed()) {
                userProfileWindow.setAlwaysOnTop(true, 'pop-up-menu');
            }
        } catch (err) {
            console.error('blur handler error:', err);
        }
    });
}

function closeUserProfileWindow() {
    if (userProfileWindow && !userProfileWindow.isDestroyed()) {
        userProfileWindow.hide();
    }
}


// ==========================================
// 视频音频分析窗口
// ==========================================

ipcMain.on('toggle-video-audio-window', () => {
    if (videoAudioWindow && !videoAudioWindow.isDestroyed()) {
        if (videoAudioWindow.isVisible()) {
            videoAudioWindow.hide();
        } else {
            videoAudioWindow.show();
            videoAudioWindow.focus();
            // 发送当前正在观看的视频ID
            if (currentBvId) {
                videoAudioWindow.webContents.send('video-change', currentBvId);
            }
        }
    } else {
        createVideoAudioWindow();
    }
});

ipcMain.on('close-video-audio-window', () => {
    closeVideoAudioWindow();
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('video-audio-window-closed');
    }
});

function createVideoAudioWindow() {
    if (videoAudioWindow && !videoAudioWindow.isDestroyed()) {
        videoAudioWindow.show();
        videoAudioWindow.focus();
        return;
    }

    const winWidth = 500;
    const winHeight = 600;
    const workArea = screen.getPrimaryDisplay().workArea;

    let x = 500, y = 300;
    if (lastWindowPosition) {
        x = lastWindowPosition.x + lastWindowPosition.width + 20;
        y = lastWindowPosition.y;
    }

    // 确保窗口在屏幕可见范围内
    x = Math.max(workArea.x, Math.min(x, workArea.x + workArea.width - winWidth));
    y = Math.max(workArea.y, Math.min(y, workArea.y + workArea.height - winHeight));

    videoAudioWindow = new BrowserWindow({
        width: winWidth,
        height: winHeight,
        x: x,
        y: y,
        frame: false,
        alwaysOnTop: true,
        transparent: true,
        resizable: false,
        skipTaskbar: true,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            enableRemoteModule: true
        },
        backgroundColor: '#00000000',
        hasShadow: false,
        focusable: true,
        show: false
    });

    videoAudioWindow.loadFile('src/video-audio-analysis.html');

    videoAudioWindow.once('ready-to-show', () => {
        videoAudioWindow.show();
        videoAudioWindow.setAlwaysOnTop(true, 'pop-up-menu');
        videoAudioWindow.setVisibleOnAllWorkspaces(true);
        // 发送当前正在观看的视频ID
        if (currentBvId) {
            videoAudioWindow.webContents.send('video-change', currentBvId);
        }
    });

    // 兜底：如果 ready-to-show 迟迟不触发，3秒后强制显示
    setTimeout(() => {
        if (videoAudioWindow && !videoAudioWindow.isDestroyed() && !videoAudioWindow.isVisible()) {
            videoAudioWindow.show();
            videoAudioWindow.setAlwaysOnTop(true, 'pop-up-menu');
            // 发送当前正在观看的视频ID
            if (currentBvId) {
                videoAudioWindow.webContents.send('video-change', currentBvId);
            }
        }
    }, 3000);

    videoAudioWindow.on('closed', () => {
        videoAudioWindow = null;
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('video-audio-window-closed');
        }
    });

    videoAudioWindow.on('blur', () => {
        try {
            if (videoAudioWindow && !videoAudioWindow.isDestroyed()) {
                videoAudioWindow.setAlwaysOnTop(true, 'pop-up-menu');
            }
        } catch (err) {
            console.error('blur handler error:', err);
        }
    });
}

function closeVideoAudioWindow() {
    if (videoAudioWindow && !videoAudioWindow.isDestroyed()) {
        videoAudioWindow.hide();
    }
}


// ==========================================
// 多模态情感分析报告窗口
// ==========================================

ipcMain.on('toggle-overall-reports-window', () => {
    if (overallReportsWindow && !overallReportsWindow.isDestroyed()) {
        if (overallReportsWindow.isVisible()) {
            overallReportsWindow.hide();
        } else {
            overallReportsWindow.show();
            overallReportsWindow.focus();
            // 发送当前视频数据
            if (currentBvId) {
                const videoData = { bvId: currentBvId, title: currentVideoTitle };
                overallReportsWindow.webContents.send('video-change', videoData);
            }
        }
    } else {
        createOverallReportsWindow();
    }
});

ipcMain.on('close-overall-reports-window', () => {
    closeOverallReportsWindow();
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('overall-reports-window-closed');
    }
});

ipcMain.on('open-overall-reports-window', () => {
    createOverallReportsWindow();
});

function createOverallReportsWindow() {
    if (overallReportsWindow && !overallReportsWindow.isDestroyed()) {
        overallReportsWindow.show();
        overallReportsWindow.focus();
        return;
    }

    const winWidth = 600;
    const winHeight = 750;
    const workArea = screen.getPrimaryDisplay().workArea;

    let x = workArea.x + workArea.width - winWidth - 50;
    let y = workArea.y + 50;

    // 如果有其他窗口位置，依次排列
    if (analysisWindow && !analysisWindow.isDestroyed()) {
        const bounds = analysisWindow.getBounds();
        x = bounds.x - winWidth - 20;
        y = bounds.y;
    }

    overallReportsWindow = new BrowserWindow({
        width: winWidth,
        height: winHeight,
        x: x,
        y: y,
        frame: false,
        alwaysOnTop: true,
        transparent: true,
        resizable: false,
        skipTaskbar: true,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            enableRemoteModule: true
        },
        backgroundColor: '#00000000',
        hasShadow: false,
        focusable: true,
        show: false
    });

    overallReportsWindow.loadFile('src/overall-reports.html');

    overallReportsWindow.once('ready-to-show', () => {
        overallReportsWindow.show();
        overallReportsWindow.setAlwaysOnTop(true, 'pop-up-menu');
        overallReportsWindow.setVisibleOnAllWorkspaces(true);
        // 发送当前视频数据
        if (currentBvId) {
            const videoData = { bvId: currentBvId, title: currentVideoTitle };
            overallReportsWindow.webContents.send('video-change', videoData);
        }
    });

    // 兜底：3秒后强制显示
    setTimeout(() => {
        if (overallReportsWindow && !overallReportsWindow.isDestroyed() && !overallReportsWindow.isVisible()) {
            overallReportsWindow.show();
            overallReportsWindow.setAlwaysOnTop(true, 'pop-up-menu');
            if (currentBvId) {
                overallReportsWindow.webContents.send('video-change', { bvId: currentBvId, title: currentVideoTitle });
            }
        }
    }, 3000);

    overallReportsWindow.on('closed', () => {
        overallReportsWindow = null;
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('overall-reports-window-closed');
        }
    });

    overallReportsWindow.on('blur', () => {
        try {
            if (overallReportsWindow && !overallReportsWindow.isDestroyed()) {
                overallReportsWindow.setAlwaysOnTop(true, 'pop-up-menu');
            }
        } catch (err) {
            console.error('blur handler error:', err);
        }
    });
}

function closeOverallReportsWindow() {
    if (overallReportsWindow && !overallReportsWindow.isDestroyed()) {
        overallReportsWindow.hide();
    }
}


// ==========================================
// 展开仪表盘窗口
// ==========================================

ipcMain.on('open-expanded-window', () => {
    createExpandedWindow();
});

ipcMain.on('close-expanded-window', () => {
    if (expandedWindow && !expandedWindow.isDestroyed()) {
        expandedWindow.hide();
    }
});

function createExpandedWindow() {
    if (expandedWindow && !expandedWindow.isDestroyed()) {
        expandedWindow.show();
        expandedWindow.focus();
        return;
    }

    const workArea = screen.getPrimaryDisplay().workArea;
    const winWidth  = Math.min(1100, workArea.width  - 80);
    const winHeight = Math.min(700,  workArea.height - 80);
    const x = Math.floor(workArea.x + (workArea.width  - winWidth)  / 2);
    const y = Math.floor(workArea.y + (workArea.height - winHeight) / 2);

    expandedWindow = new BrowserWindow({
        width:  winWidth,
        height: winHeight,
        x, y,
        frame:       true,
        resizable:   true,
        skipTaskbar: false,
        title: 'BiliMood Dashboard',
        webPreferences: {
            nodeIntegration:    true,
            contextIsolation:   false,
            enableRemoteModule: true,
        }
    });

    expandedWindow.loadFile('src/expanded-view.html');

    expandedWindow.once('ready-to-show', () => {
        expandedWindow.show();
        if (currentBvId) {
            expandedWindow.webContents.send('video-change', {
                bvId: currentBvId,
                title: currentVideoTitle
            });
        }
    });

    expandedWindow.on('closed', () => {
        expandedWindow = null;
    });
}


// ==========================================
// B站扫码登录窗口
// ==========================================

ipcMain.on('open-bilibili-login-window', () => {
    checkBilimoodLoginAndOpen();
});

// 检查 Bilimood 登录状态，然后打开 B站登录窗口
async function checkBilimoodLoginAndOpen() {
    if (!mainWindow || mainWindow.isDestroyed()) {
        console.error('主窗口不存在');
        createBilibiliLoginWindow();
        return;
    }

    // 等待页面加载完成
    if (!mainWindow.webContents.isLoading()) {
        await checkLoginAndOpen();
    } else {
        mainWindow.webContents.once('did-stop-loading', async () => {
            await checkLoginAndOpen();
        });
    }
}

async function checkLoginAndOpen() {
    console.log('检查登录状态，缓存:', cachedBilimoodLoginStatus);

    if (cachedBilimoodLoginStatus && cachedBilimoodLoginStatus.loggedIn) {
        // 已登录，打开 B站登录窗口
        createBilibiliLoginWindow();
    } else {
        // 未登录，显示提示
        console.log('未登录，显示提示');
        showLoginRequiredDialog();
    }
}

// 显示需要登录的提示对话框
function showLoginRequiredDialog() {
    const { dialog } = require('electron');

    dialog.showMessageBox(mainWindow, {
        type: 'warning',
        title: '提示',
        message: '请先登录',
        detail: '请先登录 Bilimood 账号，再绑定 B站账号\n\n你可以在首页右上角登录',
        buttons: ['确定'],
        defaultId: 0
    });
}

function createBilibiliLoginWindow() {
    if (bilibiliLoginWindow && !bilibiliLoginWindow.isDestroyed()) {
        bilibiliLoginWindow.show();
        bilibiliLoginWindow.focus();
        return;
    }

    const winWidth = 420;
    const winHeight = 520;
    const workArea = screen.getPrimaryDisplay().workArea;

    // 居中显示
    const x = Math.floor(workArea.x + (workArea.width - winWidth) / 2);
    const y = Math.floor(workArea.y + (workArea.height - winHeight) / 2);

    bilibiliLoginWindow = new BrowserWindow({
        width: winWidth,
        height: winHeight,
        x: x,
        y: y,
        frame: false,
        alwaysOnTop: true,
        transparent: true,
        resizable: false,
        skipTaskbar: true,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            enableRemoteModule: true,
            webSecurity: false,  // 允许跨域请求
            partition: 'persist:main'  // 使用持久化的 partition 共享 cookie
        },
        backgroundColor: '#1a1a2e',
        hasShadow: false,
        focusable: true,
        show: false
    });

    bilibiliLoginWindow.loadFile('src/bilibili-login.html');

    bilibiliLoginWindow.once('ready-to-show', () => {
        bilibiliLoginWindow.show();
        bilibiliLoginWindow.setAlwaysOnTop(true, 'pop-up-menu');
    });

    bilibiliLoginWindow.on('closed', () => {
        bilibiliLoginWindow = null;
    });

    bilibiliLoginWindow.on('blur', () => {
        try {
            if (bilibiliLoginWindow && !bilibiliLoginWindow.isDestroyed()) {
                bilibiliLoginWindow.setAlwaysOnTop(true, 'pop-up-menu');
            }
        } catch (err) {
            console.error('blur handler error:', err);
        }
    });
}


// ==========================================
// UI 设置广播（主窗口 → 所有子窗口）
// ==========================================

ipcMain.on('broadcast-ui-settings', (event, settings) => {
    const windows = [analysisWindow, userProfileWindow, videoAudioWindow, overallReportsWindow];
    windows.forEach(win => {
        if (win && !win.isDestroyed()) {
            win.webContents.send('apply-ui-settings', settings);
        }
    });
});

// ==========================================
// 登录状态缓存（用于 B站登录窗口）
// ==========================================

let cachedBilimoodLoginStatus = { loggedIn: false, user: null };

ipcMain.on('broadcast-login-status', (event, status) => {
    // 缓存登录状态
    cachedBilimoodLoginStatus = {
        loggedIn: status.loggedIn,
        user: status.user || null
    };
    console.log('登录状态已缓存:', cachedBilimoodLoginStatus);

    // 广播到子窗口
    const windows = [analysisWindow, userProfileWindow, videoAudioWindow];
    windows.forEach(win => {
        if (win && !win.isDestroyed()) {
            win.webContents.send('sync-login-status', status);
        }
    });
});

// ==========================================
// 调试：打开开发者工具
// ==========================================

ipcMain.on('open-devtools', (event, windowName = 'all') => {
    // 为指定窗口或所有窗口打开开发者工具
    const windows = [];

    if (windowName === 'all' || windowName === 'main') {
        if (mainWindow && !mainWindow.isDestroyed()) windows.push(mainWindow);
    }
    if (windowName === 'all' || windowName === 'analysis') {
        if (analysisWindow && !analysisWindow.isDestroyed()) windows.push(analysisWindow);
    }
    if (windowName === 'all' || windowName === 'user') {
        if (userProfileWindow && !userProfileWindow.isDestroyed()) windows.push(userProfileWindow);
    }
    if (windowName === 'all' || windowName === 'video') {
        if (videoAudioWindow && !videoAudioWindow.isDestroyed()) windows.push(videoAudioWindow);
    }

    windows.forEach(win => {
        try {
            win.webContents.openDevTools({ mode: 'detach' });
        } catch (err) {
            console.error('打开开发者工具失败:', err);
        }
    });

    if (windows.length === 0) {
        console.log('没有找到指定的窗口');
    }
});

// ==========================================
// 监听主窗口发送的视频切换信号
// ==========================================

ipcMain.on('main-video-change', (event, data) => {
    const { bvId, title, forceRefresh } = data;

    // 更新当前视频ID
    currentBvId = bvId;
    console.log('[Main] 收到视频切换信号:', bvId, title, 'forceRefresh:', forceRefresh);

    // 如果是强制刷新模式，直接发送信号给前端
    if (forceRefresh) {
        broadcastVideoChange(bvId, title);
        return;
    }

    // 根据分析模式决定是否发送信号
    if (analysisMode === 'online') {
        // 在线模式：发送信号给前端渲染
        broadcastVideoChange(bvId, title);
    } else {
        // 历史模式：浏览器扩展的请求存入数据库，不渲染到前端
        console.log('[Main] 历史模式：视频数据已存入后台，前端不渲染');
    }
});

// ==========================================
// 广播视频切换信号到所有窗口
// ==========================================
function broadcastVideoChange(bvId, title) {
    const videoData = { bvId, title: title || '未知标题' };

    const windows = [
        mainWindow, analysisWindow, userProfileWindow,
        videoAudioWindow, expandedWindow
    ];
    windows.forEach(win => {
        if (win && !win.isDestroyed()) {
            win.webContents.send('video-change', videoData);
        }
    });
}

// ==========================================
// 监听前端发来的模式切换信号
// ==========================================
ipcMain.on('set-analysis-mode', (event, mode) => {
    if (mode === 'online' || mode === 'history') {
        analysisMode = mode;
        console.log('[Main] 分析模式已切换为:', analysisMode);

        if (mode === 'online') {
            // 切换到在线模式时，清除前端的历史数据，等待接收浏览器扩展的新数据
            console.log('[Main] 切换到在线模式，清除历史数据，等待浏览器扩展新数据');
            broadcastToAll('clear-video-data');
        } else {
            // 切换到历史模式，如果当前有视频，刷新显示
            if (currentBvId) {
                broadcastVideoChange(currentBvId);
            }
        }
    }
});

// ==========================================
// 广播消息到所有窗口
// ==========================================
function broadcastToAll(channel, data) {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send(channel, data);
    }
    const windows = [analysisWindow, userProfileWindow, videoAudioWindow];
    windows.forEach(win => {
        if (win && !win.isDestroyed()) {
            win.webContents.send(channel, data);
        }
    });
}
