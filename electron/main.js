const { app, BrowserWindow, ipcMain, screen, Tray, Menu, nativeImage } = require('electron');
app.isQuitting = false;
const path = require('path');
const WebSocket = require('ws');

// 保持对window对象的全局引用
let mainWindow;
let analysisWindow; // 情感分析窗口
let userProfileWindow; // 用户画像窗口
let videoAudioWindow; // 视频音频分析窗口
let wss; // WebSocket服务器，用于与Chrome插件通信
let tray = null; // 系统托盘
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
                    // 向主窗口发送信号
                    if (mainWindow && !mainWindow.isDestroyed()) {
                        mainWindow.webContents.send('video-change', message.bvId);
                    }
                    // 向分析窗口发送信号
                    if (analysisWindow && !analysisWindow.isDestroyed()) {
                        analysisWindow.webContents.send('video-change', message.bvId);
                    }
                    // 向用户画像窗口发送信号
                    if (userProfileWindow && !userProfileWindow.isDestroyed()) {
                        userProfileWindow.webContents.send('video-change', message.bvId);
                    }
                    // 向视频音频分析窗口发送信号
                    if (videoAudioWindow && !videoAudioWindow.isDestroyed()) {
                        videoAudioWindow.webContents.send('video-change', message.bvId);
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
  createWindow();
  createTray();
  createWebSocketServer();

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
    });

    setTimeout(() => {
        if (analysisWindow && !analysisWindow.isDestroyed() && !analysisWindow.isVisible()) {
            analysisWindow.show();
            analysisWindow.setAlwaysOnTop(true, 'pop-up-menu');
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
    });

    setTimeout(() => {
        if (userProfileWindow && !userProfileWindow.isDestroyed() && !userProfileWindow.isVisible()) {
            userProfileWindow.show();
            userProfileWindow.setAlwaysOnTop(true, 'pop-up-menu');
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
    });

    // 兜底：如果 ready-to-show 迟迟不触发，3秒后强制显示
    setTimeout(() => {
        if (videoAudioWindow && !videoAudioWindow.isDestroyed() && !videoAudioWindow.isVisible()) {
            videoAudioWindow.show();
            videoAudioWindow.setAlwaysOnTop(true, 'pop-up-menu');
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
// UI 设置广播（主窗口 → 所有子窗口）
// ==========================================

ipcMain.on('broadcast-ui-settings', (event, settings) => {
    const windows = [analysisWindow, userProfileWindow, videoAudioWindow];
    windows.forEach(win => {
        if (win && !win.isDestroyed()) {
            win.webContents.send('apply-ui-settings', settings);
        }
    });
});
