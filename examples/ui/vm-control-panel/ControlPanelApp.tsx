import React, { useEffect, useMemo, useState } from 'react';
import ControlPanel, { VmInstance, VmResource } from './ControlPanel';
import './control-panel.css';

type Toast = { id: string; message: string; tone: 'success' | 'error' | 'info' };

type DesktopBridge = {
  notify?: (payload: { title: string; body: string; tone?: Toast['tone'] }) => void;
  setPanelVisibility?: (state: 'show' | 'hide') => void;
  setAlwaysOnTop?: (flag: boolean) => void;
  onAuthToken?: (listener: (token: string) => void) => void;
  requestAuthToken?: () => Promise<string | undefined>;
};

declare global {
  interface Window {
    desktopBridge?: DesktopBridge;
  }
}

type VmUpdate = Partial<VmInstance> & { id: string };

type Action = 'launch' | 'stop' | 'screenshot' | 'send-command';

type ApiResponse<T> = { data?: T; message?: string };

class CuaApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly wsUrl: string,
    private readonly authToken?: string
  ) {}

  private async post<T>(path: string, body?: Record<string, unknown>): Promise<ApiResponse<T>> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(this.authToken ? { Authorization: `Bearer ${this.authToken}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!res.ok) {
      const message = await res.text();
      throw new Error(message || `HTTP ${res.status}`);
    }

    const json = await res.json().catch(() => undefined);
    return json ?? { message: 'ok' };
  }

  launchVm(id: string) {
    return this.post(`/computer/v1/vms/${id}/launch`);
  }

  stopVm(id: string) {
    return this.post(`/computer/v1/vms/${id}/stop`);
  }

  screenshot(id: string) {
    return this.post<{ snapshotUrl: string }>(`/computer/v1/vms/${id}/screenshot`);
  }

  sendCommand(id: string, command: string) {
    return this.post(`/computer/v1/vms/${id}/input`, { command });
  }

  fetchLogs(id: string) {
    return this.post<{ logs: string[] }>(`/computer/v1/vms/${id}/logs`);
  }

  streamVmUpdates(onUpdate: (update: VmUpdate) => void) {
    const wsUrl = new URL(`${this.wsUrl}/computer/v1/vms/stream`);
    if (this.authToken) {
      wsUrl.searchParams.set('token', this.authToken);
    }
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      onUpdate(payload as VmUpdate);
    };
    return () => ws.close();
  }
}

function mergeUpdate(prev: VmInstance[], update: VmUpdate): VmInstance[] {
  const next = [...prev];
  const index = next.findIndex((vm) => vm.id === update.id);
  const merged: VmInstance = {
    id: update.id,
    name: update.name ?? `VM-${update.id}`,
    status: update.status ?? 'idle',
    snapshotUrl: update.snapshotUrl,
    lastCommand: update.lastCommand,
    lastResult: update.lastResult,
    resource: update.resource as VmResource | undefined,
    recentLogLine: update.recentLogLine,
    busyLabel: update.busyLabel,
  };

  if (index >= 0) {
    next[index] = { ...next[index], ...merged };
  } else {
    next.push(merged);
  }
  return next;
}

export function ControlPanelApp() {
  const [authToken, setAuthToken] = useState<string | undefined>();
  const [isPinned, setIsPinned] = useState(true);
  const client = useMemo(
    () => new CuaApiClient('http://localhost:8000', 'ws://localhost:8000', authToken),
    [authToken]
  );
  const [instances, setInstances] = useState<VmInstance[]>([
    { id: 'vm-01', name: 'Workspace', status: 'idle', resource: { cpu: 7, memoryMb: 512 } },
    { id: 'vm-02', name: 'Browser sand-box', status: 'launching', resource: { cpu: 21, memoryMb: 1024 } },
  ]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const bridge = window.desktopBridge;
    bridge?.onAuthToken?.((token) => setAuthToken(token));
    bridge?.requestAuthToken?.().then((token) => token && setAuthToken(token));
  }, []);

  useEffect(() => {
    const stop = client.streamVmUpdates((update) => {
      setInstances((prev) => mergeUpdate(prev, update));
      if (update.lastResult) {
        pushToast({
          id: `${update.id}-result`,
          message: update.lastResult,
          tone: 'success',
        });
      }
    });
    return stop;
  }, [client]);

  const pushToast = (toast: Toast) => {
    setToasts((prev) => [...prev, toast]);
    sendDesktopNotification(toast.message, toast.tone);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== toast.id));
    }, 3600);
  };

  const sendDesktopNotification = (message: string, tone: Toast['tone']) => {
    if (typeof window === 'undefined') return;
    window.desktopBridge?.notify?.({ title: 'Cua Control Panel', body: message, tone });
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('Cua Control Panel', { body: message });
    } else if ('Notification' in window && Notification.permission !== 'denied') {
      Notification.requestPermission();
    }
  };

  const handleAction = async (id: string, action: Action, commandText?: string) => {
    setInstances((prev) =>
      prev.map((vm) => (vm.id === id ? { ...vm, busyLabel: action, lastResult: undefined } : vm))
    );

    const label = action === 'send-command' ? 'Command executed' : `${action} requested`;

    try {
      if (action === 'launch') await client.launchVm(id);
      if (action === 'stop') await client.stopVm(id);
      if (action === 'screenshot') {
        const res = await client.screenshot(id);
        if (res.data?.snapshotUrl) {
          setInstances((prev) =>
            prev.map((vm) => (vm.id === id ? { ...vm, snapshotUrl: res.data?.snapshotUrl } : vm))
          );
          pushToast({ id: `${id}-screenshot`, message: 'Screenshot saved', tone: 'success' });
        }
      }
      if (action === 'send-command') {
        const text = commandText ?? drafts[id] ?? '';
        await client.sendCommand(id, text);
      }
      pushToast({ id: `${id}-${action}`, message: label, tone: 'info' });
    } catch (err) {
      pushToast({ id: `${id}-${action}-error`, message: (err as Error).message, tone: 'error' });
    } finally {
      setInstances((prev) => prev.map((vm) => (vm.id === id ? { ...vm, busyLabel: undefined } : vm)));
    }
  };

  const handleCommand = async (id: string, text: string) => {
    setDrafts((prev) => ({ ...prev, [id]: text }));
    if (!text) return;
    await handleAction(id, 'send-command', text);
  };

  const handleInspectLogs = async (id: string) => {
    try {
      const res = await client.fetchLogs(id);
      const tail = res.data?.logs?.slice(-1)?.[0];
      if (tail) {
        setInstances((prev) =>
          prev.map((vm) => (vm.id === id ? { ...vm, recentLogLine: tail, lastResult: tail } : vm))
        );
        pushToast({ id: `${id}-logs`, message: 'Agent log updated', tone: 'info' });
      }
    } catch (err) {
      pushToast({ id: `${id}-logs-error`, message: (err as Error).message, tone: 'error' });
    }
  };

  return (
    <div className="cua-panel__layout">
      <ControlPanel instances={instances} onAction={handleAction} onCommandText={handleCommand} />
      <div className="cua-panel__actions-row">
        {instances.map((vm) => (
          <button key={vm.id} className="cua-ghost" onClick={() => handleInspectLogs(vm.id)}>
            View agent logs · {vm.name}
          </button>
        ))}
        <button
          className="cua-ghost"
          onClick={() => {
            const next = !isPinned;
            setIsPinned(next);
            window.desktopBridge?.setAlwaysOnTop?.(next);
          }}
        >
          {isPinned ? 'Unpin panel (disable always-on-top)' : 'Pin panel (always-on-top)'}
        </button>
        <button className="cua-ghost" onClick={() => window.desktopBridge?.setPanelVisibility?.('hide')}>
          Send to tray
        </button>
      </div>

      <div className="cua-toast-shelf" aria-live="assertive">
        {toasts.map((toast) => (
          <div key={toast.id} className={`cua-toast cua-toast--${toast.tone}`}>
            <span className="cua-pulse" aria-hidden />
            {toast.message}
          </div>
        ))}
      </div>
    </div>
  );
}

export default ControlPanelApp;
