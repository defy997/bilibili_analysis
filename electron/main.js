const { app, BrowserWindow, ipcMain, screen } = require('electron');
const path = require('path');
const WebSocket = require('ws');

// 保持对window对象的全局引用
let mainWindow;
let analysisWindow; // 情感分析窗口
let wss; // WebSocket服务器，用于与Chrome插件通信
let miniWindow; // 最小化后的小图标窗口
let lastWindowPosition = null; // 记录上次主窗口位置以便还原

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
      enableRemoteModule: true
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

  // 当窗口最小化时，隐藏主窗口并显示小图标窗口
  mainWindow.on('minimize', (event) => {
    try {
      event.preventDefault();
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.hide();
        showMiniWindow();
      }
    } catch (err) {
      console.error('minimize handler error:', err);
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
                    // 向主窗口发送信号
                    if (mainWindow && !mainWindow.isDestroyed()) {
                        mainWindow.webContents.send('video-change', message.bvId);
                    }
                    // 向分析窗口发送信号
                    if (analysisWindow && !analysisWindow.isDestroyed()) {
                        analysisWindow.webContents.send('video-change', message.bvId);
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

// Electron 会在初始化后并准备创建浏览器窗口时，调用这个函数
app.whenReady().then(() => {
  createWindow();
  createWebSocketServer();

  app.on('activate', () => {
    // 在macOS上，当单击dock图标并且没有其他窗口打开时，
    // 通常在应用中重新创建一个窗口
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
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
});

// 监听渲染进程的消息
ipcMain.on('minimize-window', () => {
  // 隐藏主窗口并显示小图标窗口（保持置顶）
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.hide();
    showMiniWindow();
  }
});

ipcMain.on('close-window', () => {
  if (mainWindow) mainWindow.close();
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

// 还原主窗口（从小图标窗口点击触发）
ipcMain.on('restore-window', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.show();
        mainWindow.focus();
    }
    destroyMiniWindow();
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
});

// 打开分析窗口
ipcMain.on('open-analysis-window', () => {
    createAnalysisWindow();
});

// 小图标右键菜单（还原/退出）
ipcMain.on('show-mini-context-menu', () => {
  try {
    const { Menu } = require('electron');
    const template = [
      { label: '还原悬浮窗', click: () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); destroyMiniWindow(); } } },
      { type: 'separator' },
      { label: '退出悬浮窗', click: () => { app.quit(); } }
    ];
    const menu = Menu.buildFromTemplate(template);
    menu.popup();
  } catch (err) {
    console.error('show-mini-context-menu error:', err);
  }
});

// 拖拽支持：渲染进程调用以获取当前 miniWindow bounds，然后发送更新位置
ipcMain.handle('mini-begin-drag', (event, pos) => {
  try {
    if (miniWindow && !miniWindow.isDestroyed()) {
      return miniWindow.getBounds();
    }
  } catch (err) {
    console.error('mini-begin-drag handler error:', err);
  }
  // fallback
  return { x: 0, y: 0, width: 64, height: 64 };
});

ipcMain.on('mini-update-drag', (event, data) => {
  try {
    if (!miniWindow || miniWindow.isDestroyed()) return;
    const { screenX, screenY, offsetX, offsetY } = data;
    const workArea = screen.getDisplayNearestPoint({ x: screenX, y: screenY }).workArea;
    const newX = Math.max(workArea.x, Math.min(screenX - offsetX, workArea.x + workArea.width - (miniWindow.getBounds().width || 64)));
    const newY = Math.max(workArea.y, Math.min(screenY - offsetY, workArea.y + workArea.height - (miniWindow.getBounds().height || 64)));
    miniWindow.setBounds({ x: Math.round(newX), y: Math.round(newY) });
  } catch (err) {
    console.error('mini-update-drag error:', err);
  }
});

// 创建并显示小图标窗口
function showMiniWindow() {
  try {
    if (miniWindow && !miniWindow.isDestroyed()) {
      miniWindow.show();
      miniWindow.focus();
      return;
    }

    // 小图标窗口尺寸与样式，位置优先使用 lastWindowPosition，否则使用光标位置
    const miniSize = { w: 64, h: 64 };
    let miniX, miniY;
    try {
      if (lastWindowPosition && lastWindowPosition.x !== undefined) {
        // 放在主窗口右下角附近
        miniX = lastWindowPosition.x + (lastWindowPosition.width || 0) - Math.floor(miniSize.w * 0.7);
        miniY = lastWindowPosition.y + (lastWindowPosition.height || 0) - Math.floor(miniSize.h * 0.7);
      } else {
        const cursor = screen.getCursorScreenPoint();
        miniX = cursor.x - Math.floor(miniSize.w / 2);
        miniY = cursor.y - Math.floor(miniSize.h / 2);
      }

      // 限制在工作区范围内
      const workArea = screen.getDisplayNearestPoint(screen.getCursorScreenPoint()).workArea;
      miniX = Math.max(workArea.x, Math.min(miniX, workArea.x + workArea.width - miniSize.w));
      miniY = Math.max(workArea.y, Math.min(miniY, workArea.y + workArea.height - miniSize.h));
    } catch (err) {
      miniX = undefined;
      miniY = undefined;
    }

    miniWindow = new BrowserWindow({
      width: miniSize.w,
      height: miniSize.h,
      x: miniX,
      y: miniY,
      frame: false,
      alwaysOnTop: true,
      transparent: true,
      resizable: false,
      skipTaskbar: true,
      movable: true,
      focusable: true,
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false
      }
    });

    miniWindow.loadFile(path.join(__dirname, 'src', 'mini.html'));

    miniWindow.on('closed', () => {
      miniWindow = null;
    });

    // 点击小图标时还原主窗口（由mini.html发送ipc消息）
    // 另：如果主窗口被关闭，也要关闭miniWindow
    if (mainWindow) {
      mainWindow.on('closed', () => {
        destroyMiniWindow();
      });
    }
  } catch (err) {
    console.error('showMiniWindow error:', err);
  }
}

function destroyMiniWindow() {
  try {
    if (miniWindow && !miniWindow.isDestroyed()) {
      miniWindow.close();
      miniWindow = null;
    }
  } catch (err) {
    console.error('destroyMiniWindow error:', err);
  }
}

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

    // 位置在主窗口右边
    let x = 500, y = 300;
    if (lastWindowPosition) {
        x = lastWindowPosition.x + lastWindowPosition.width + 20;
        y = lastWindowPosition.y;
    }

    analysisWindow = new BrowserWindow({
        width: 500,
        height: 600,
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
    });

    analysisWindow.on('closed', () => {
        analysisWindow = null;
    });

    // 失去焦点时重申置顶
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
