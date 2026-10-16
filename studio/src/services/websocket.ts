import { useStudioStore } from '../store/useStudioStore';

class WebSocketManager {
  private logSocket: WebSocket | null = null;
  private telemetrySocket: WebSocket | null = null;

  private shouldReconnect = true;
  private logReconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private telemetryReconnectTimer: ReturnType<typeof setTimeout> | null = null;

  private logAttempts = 0;
  private telemetryAttempts = 0;
  private readonly MIN_BACKOFF_MS = 1000;
  private readonly MAX_BACKOFF_MS = 30000;

  // Log buffer for batching updates to Zustand store every 100ms
  private logBuffer: string[] = [];
  private logFlushTimer: ReturnType<typeof setInterval> | null = null;
  private readonly FLUSH_INTERVAL_MS = 100;

  private getBackoffDelay(attempts: number): number {
    const base = Math.min(this.MAX_BACKOFF_MS, this.MIN_BACKOFF_MS * Math.pow(2, attempts));
    const jitter = Math.random() * 0.3 * base; // 0-30% randomized jitter to prevent thundering herds
    return Math.min(this.MAX_BACKOFF_MS, base + jitter);
  }

  private enqueueLog(msg: string) {
    this.logBuffer.push(msg);
    if (!this.logFlushTimer) {
      this.logFlushTimer = setInterval(() => this.flushLogs(), this.FLUSH_INTERVAL_MS);
    }
  }

  private flushLogs() {
    if (this.logBuffer.length === 0) return;
    const batch = this.logBuffer;
    this.logBuffer = [];
    useStudioStore.getState().appendLogs(batch);
  }

  connect() {
    this.shouldReconnect = true;
    this.connectLogs();
    this.connectTelemetry();
  }

  private connectLogs() {
    if (!this.shouldReconnect) return;
    if (
      this.logSocket &&
      (this.logSocket.readyState === WebSocket.CONNECTING ||
        this.logSocket.readyState === WebSocket.OPEN)
    ) {
      return;
    }

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;

    try {
      this.logSocket = new WebSocket(`${proto}//${host}/ws/logs`);

      this.logSocket.onopen = () => {
        this.logAttempts = 0;
      };

      this.logSocket.onmessage = (event) => {
        if (event.data) {
          this.enqueueLog(event.data);
        }
      };

      this.logSocket.onerror = (e) => {
        console.warn('Log WebSocket error:', e);
      };

      this.logSocket.onclose = () => {
        this.logSocket = null;
        if (!this.shouldReconnect) return;
        const delay = this.getBackoffDelay(this.logAttempts++);
        this.logReconnectTimer = setTimeout(() => this.connectLogs(), delay);
      };
    } catch (e) {
      console.warn('Log WebSocket connection failed:', e);
      if (this.shouldReconnect) {
        const delay = this.getBackoffDelay(this.logAttempts++);
        this.logReconnectTimer = setTimeout(() => this.connectLogs(), delay);
      }
    }
  }

  private connectTelemetry() {
    if (!this.shouldReconnect) return;
    if (
      this.telemetrySocket &&
      (this.telemetrySocket.readyState === WebSocket.CONNECTING ||
        this.telemetrySocket.readyState === WebSocket.OPEN)
    ) {
      return;
    }

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;

    try {
      this.telemetrySocket = new WebSocket(`${proto}//${host}/ws/telemetry`);

      this.telemetrySocket.onopen = () => {
        this.telemetryAttempts = 0;
        useStudioStore.getState().setWsConnected(true);
      };

      this.telemetrySocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'telemetry') {
            useStudioStore.getState().updateLiveTelemetry(data);
          }
        } catch (e) {}
      };

      this.telemetrySocket.onerror = (e) => {
        console.warn('Telemetry WebSocket error:', e);
      };

      this.telemetrySocket.onclose = () => {
        this.telemetrySocket = null;
        useStudioStore.getState().setWsConnected(false);
        if (!this.shouldReconnect) return;
        const delay = this.getBackoffDelay(this.telemetryAttempts++);
        this.telemetryReconnectTimer = setTimeout(() => this.connectTelemetry(), delay);
      };
    } catch (e) {
      console.warn('Telemetry WebSocket connection failed:', e);
      useStudioStore.getState().setWsConnected(false);
      if (this.shouldReconnect) {
        const delay = this.getBackoffDelay(this.telemetryAttempts++);
        this.telemetryReconnectTimer = setTimeout(() => this.connectTelemetry(), delay);
      }
    }
  }

  disconnect() {
    this.shouldReconnect = false;

    if (this.logReconnectTimer) {
      clearTimeout(this.logReconnectTimer);
      this.logReconnectTimer = null;
    }
    if (this.telemetryReconnectTimer) {
      clearTimeout(this.telemetryReconnectTimer);
      this.telemetryReconnectTimer = null;
    }
    if (this.logFlushTimer) {
      clearInterval(this.logFlushTimer);
      this.logFlushTimer = null;
    }

    this.flushLogs();

    if (this.logSocket) {
      this.logSocket.onclose = null;
      this.logSocket.close();
      this.logSocket = null;
    }

    if (this.telemetrySocket) {
      this.telemetrySocket.onclose = null;
      this.telemetrySocket.close();
      this.telemetrySocket = null;
    }

    useStudioStore.getState().setWsConnected(false);
  }
}

export const wsManager = new WebSocketManager();
