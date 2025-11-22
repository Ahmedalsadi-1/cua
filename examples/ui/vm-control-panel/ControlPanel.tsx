import React, { useMemo, useState } from 'react';
import './control-panel.css';

export type VmStatus = 'running' | 'idle' | 'error' | 'launching';

export interface VmResource {
  cpu: number;
  memoryMb: number;
  networkMbps?: number;
}

export interface VmInstance {
  id: string;
  name: string;
  status: VmStatus;
  snapshotUrl?: string;
  lastCommand?: string;
  lastResult?: string;
  busyLabel?: string;
  resource?: VmResource;
  recentLogLine?: string;
}

type PanelTheme = 'dark' | 'carbon' | 'plasma';

interface ControlPanelProps {
  instances: VmInstance[];
  onAction?: (id: string, action: 'launch' | 'stop' | 'screenshot' | 'send-command') => void;
  onCommandText?: (id: string, text: string) => void;
  defaultCollapsed?: boolean;
}

const statusTone: Record<VmStatus, string> = {
  running: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/60',
  idle: 'bg-slate-500/20 text-slate-200 border-slate-500/60',
  error: 'bg-rose-500/20 text-rose-200 border-rose-500/60',
  launching: 'bg-amber-500/20 text-amber-200 border-amber-500/60',
};

const statusLabel: Record<VmStatus, string> = {
  running: 'Running',
  idle: 'Idle',
  error: 'Error',
  launching: 'Launching',
};

export function ControlPanel({
  instances,
  onAction,
  onCommandText,
  defaultCollapsed = false,
}: ControlPanelProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const [touchStartX, setTouchStartX] = useState<number | null>(null);
  const [draftCommands, setDraftCommands] = useState<Record<string, string>>({});
  const themes: PanelTheme[] = ['dark', 'carbon', 'plasma'];
  const [themeIndex, setThemeIndex] = useState(0);
  const theme = themes[themeIndex % themes.length];

  const liveCounts = useMemo(
    () => ({
      running: instances.filter((vm) => vm.status === 'running').length,
      idle: instances.filter((vm) => vm.status === 'idle').length,
      error: instances.filter((vm) => vm.status === 'error').length,
    }),
    [instances]
  );

  const handleSwipe = (deltaX: number) => {
    const threshold = 40; // adjust to taste
    if (deltaX > threshold) setCollapsed(true);
    if (deltaX < -threshold) setCollapsed(false);
  };

  return (
    <div
      className={`cua-panel ${collapsed ? 'collapsed' : 'expanded'}`}
      data-theme={theme}
      onTouchStart={(e) => setTouchStartX(e.touches[0].clientX)}
      onTouchMove={(e) => touchStartX !== null && handleSwipe(e.touches[0].clientX - touchStartX)}
      onTouchEnd={() => setTouchStartX(null)}
    >
      <div className="cua-panel__rails" aria-hidden />
      <div className="cua-panel__rail-dot" aria-hidden />
      <div className={`cua-mascot ${collapsed ? 'cua-mascot--hidden' : ''}`} aria-hidden>
        <div className="cua-mascot__body">🐇</div>
        <p className="cua-mascot__tag">Agent bunny online</p>
      </div>

      <header className="cua-panel__header">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-cyan-300/70">VM control panel</p>
          <h3 className="text-lg font-semibold text-slate-50">Desktop automation cockpit</h3>
          <p className="text-sm text-slate-300/80">Hybrid TUI/GUI with live status + quick actions</p>
        </div>
        <div className="cua-panel__header-actions">
          <button
            type="button"
            className="cua-toggle"
            onClick={() => setThemeIndex((i) => i + 1)}
            aria-label="Toggle panel theme"
          >
            Theme: {theme}
          </button>
          <button
            type="button"
            className="cua-toggle"
            onClick={() => setCollapsed((v) => !v)}
            aria-label={collapsed ? 'Expand panel' : 'Collapse panel'}
          >
            {collapsed ? '▣' : '☰'}
          </button>
        </div>
      </header>

      <div className="cua-panel__summary">
        <div>
          <span className="label">Running</span>
          <strong>{liveCounts.running}</strong>
        </div>
        <div>
          <span className="label">Idle</span>
          <strong>{liveCounts.idle}</strong>
        </div>
        <div>
          <span className="label">Errors</span>
          <strong>{liveCounts.error}</strong>
        </div>
      </div>

      <section className="cua-panel__instances">
        {instances.map((vm) => (
          <article key={vm.id} className="cua-card">
            <div className="cua-card__header">
              <div>
                <p className="text-[11px] uppercase tracking-[0.2em] text-cyan-200/60">{vm.id}</p>
                <h4 className="text-base text-slate-50 font-semibold">{vm.name}</h4>
              </div>
              <span className={`cua-pill ${statusTone[vm.status]}`}>
                <span className="cua-pulse" aria-hidden />
                {statusLabel[vm.status]}
              </span>
            </div>

            <div className="cua-card__body">
              <div className="cua-snapshot" aria-label={`Snapshot for ${vm.name}`}>
                {vm.snapshotUrl ? (
                  <img src={vm.snapshotUrl} alt={`VM ${vm.name} snapshot`} />
                ) : (
                  <div className="cua-snapshot__placeholder">
                    <span className="text-cyan-200/80">No snapshot yet</span>
                  </div>
                )}
              </div>

              <div className="cua-actions">
                <button disabled={!!vm.busyLabel} onClick={() => onAction?.(vm.id, 'launch')}>
                  {vm.busyLabel === 'launch' ? <span className="cua-spinner" aria-label="Launching" /> : 'Launch'}
                </button>
                <button disabled={!!vm.busyLabel} onClick={() => onAction?.(vm.id, 'stop')}>
                  {vm.busyLabel === 'stop' ? <span className="cua-spinner" aria-label="Stopping" /> : 'Stop'}
                </button>
                <button disabled={!!vm.busyLabel} onClick={() => onAction?.(vm.id, 'screenshot')}>
                  {vm.busyLabel === 'screenshot' ? (
                    <span className="cua-spinner" aria-label="Capturing" />
                  ) : (
                    'Screenshot'
                  )}
                </button>
                <button disabled={!!vm.busyLabel} onClick={() => onAction?.(vm.id, 'send-command')}>
                  {vm.busyLabel === 'send-command' ? (
                    <span className="cua-spinner" aria-label="Sending" />
                  ) : (
                    'Send command'
                  )}
                </button>
              </div>

              <label className="cua-command">
                <span>Command</span>
                <input
                  type="text"
                  value={draftCommands[vm.id] ?? vm.lastCommand ?? ''}
                  onChange={(e) =>
                    setDraftCommands((prev) => ({ ...prev, [vm.id]: e.target.value }))
                  }
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      const text = draftCommands[vm.id] ?? '';
                      onCommandText?.(vm.id, text);
                    }
                  }}
                  placeholder="type to send..."
                />
              </label>

              {vm.resource && (
                <div className="cua-metrics" aria-label={`Resource usage for ${vm.name}`}>
                  <div>
                    <span className="label">CPU</span>
                    <strong>{vm.resource.cpu.toFixed(0)}%</strong>
                  </div>
                  <div>
                    <span className="label">Memory</span>
                    <strong>{vm.resource.memoryMb.toFixed(0)} MB</strong>
                  </div>
                  {vm.resource.networkMbps !== undefined && (
                    <div>
                      <span className="label">Network</span>
                      <strong>{vm.resource.networkMbps.toFixed(1)} Mbps</strong>
                    </div>
                  )}
                </div>
              )}

              {(vm.lastResult || vm.recentLogLine) && (
                <div className="cua-logline" aria-live="polite">
                  <span className="label">Last message</span>
                  <p>{vm.lastResult ?? vm.recentLogLine}</p>
                </div>
              )}
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}

export default ControlPanel;
