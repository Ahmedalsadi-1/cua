import { app, BrowserWindow, globalShortcut, ipcMain, Menu, nativeImage, Notification, shell, Tray } from 'electron';
import path from 'path';

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let pinned = true;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 640,
    backgroundColor: '#0b1220',
    show: false,
    autoHideMenuBar: true,
    titleBarStyle: 'hiddenInset',
    alwaysOnTop: pinned,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  mainWindow.loadURL(process.env.CUA_PANEL_URL || 'http://localhost:3000');

  mainWindow.on('ready-to-show', () => mainWindow?.show());
  mainWindow.on('close', (event) => {
    // Minimize to tray instead of quitting so background hotkeys keep working.
    if (!app.isQuiting) {
      event.preventDefault();
      mainWindow?.hide();
    }
  });
}

function createTray() {
  const iconPath = path.join(__dirname, 'tray-icon.png');
  const icon = nativeImage.createFromPath(iconPath);
  tray = new Tray(icon.isEmpty() ? undefined : icon);
  const menu = Menu.buildFromTemplate([
    { label: 'Show panel', click: () => showPanel() },
    { label: pinned ? 'Disable always-on-top' : 'Enable always-on-top', click: () => toggleAlwaysOnTop() },
    { type: 'separator' },
    { label: 'Open docs', click: () => shell.openExternal('https://github.com/Ahmedalsadi-1/cua') },
    { type: 'separator' },
    { label: 'Quit', click: () => quitApp() },
  ]);
  tray.setToolTip('Cua VM Control Panel');
  tray.setContextMenu(menu);
  tray.on('click', () => showPanel());
}

function registerShortcuts() {
  globalShortcut.register('CommandOrControl+Shift+K', () => showPanel());
  globalShortcut.register('CommandOrControl+Shift+H', () => mainWindow?.hide());
}

function showPanel() {
  if (!mainWindow) return;
  mainWindow.show();
  mainWindow.focus();
}

function toggleAlwaysOnTop(flag?: boolean) {
  if (!mainWindow) return;
  pinned = flag ?? !pinned;
  mainWindow.setAlwaysOnTop(pinned, 'floating');
  mainWindow.webContents.send('panel:pin-changed', pinned);
}

function sendNotification({ title, body }: { title: string; body: string }) {
  const notice = new Notification({
    title,
    body,
    silent: false,
  });
  notice.show();
}

function quitApp() {
  app.isQuiting = true as unknown as boolean;
  app.quit();
}

app.whenReady().then(() => {
  createWindow();
  createTray();
  registerShortcuts();

  ipcMain.handle('notify', (_event, payload) => {
    sendNotification(payload);
  });

  ipcMain.handle('set-always-on-top', (_event, flag: boolean) => toggleAlwaysOnTop(flag));

  ipcMain.handle('set-panel-visibility', (_event, state: 'show' | 'hide') => {
    if (state === 'show') showPanel();
    if (state === 'hide') mainWindow?.hide();
  });

  ipcMain.handle('request-auth-token', () => process.env.CUA_PANEL_TOKEN);
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('before-quit', () => {
  globalShortcut.unregisterAll();
});
