import { contextBridge, ipcRenderer } from 'electron';

type NotifyPayload = { title: string; body: string; tone?: 'success' | 'error' | 'info' };

declare global {
  interface Window {
    desktopBridge?: {
      notify: (payload: NotifyPayload) => Promise<void>;
      setPanelVisibility: (state: 'show' | 'hide') => Promise<void>;
      setAlwaysOnTop: (flag: boolean) => Promise<void>;
      onAuthToken: (listener: (token: string) => void) => void;
      requestAuthToken: () => Promise<string | undefined>;
    };
  }
}

contextBridge.exposeInMainWorld('desktopBridge', {
  notify: (payload: NotifyPayload) => ipcRenderer.invoke('notify', payload),
  setPanelVisibility: (state: 'show' | 'hide') => ipcRenderer.invoke('set-panel-visibility', state),
  setAlwaysOnTop: (flag: boolean) => ipcRenderer.invoke('set-always-on-top', flag),
  onAuthToken: (listener: (token: string) => void) => ipcRenderer.on('auth-token', (_event, token) => listener(token)),
  requestAuthToken: () => ipcRenderer.invoke('request-auth-token'),
});
