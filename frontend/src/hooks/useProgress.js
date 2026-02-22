import { useState, useEffect, useRef, useCallback } from 'react';

export function useProgress() {
  const [progress, setProgress] = useState({ pct: 0, message: '' });
  const wsRef = useRef(null);

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${window.location.host}/ws/progress`;

    function connect() {
      const ws = new WebSocket(url);
      wsRef.current = ws;
      ws.onmessage = (e) => {
        try { setProgress(JSON.parse(e.data)); } catch {}
      };
      ws.onclose = () => setTimeout(connect, 2000);
      ws.onerror = () => ws.close();
    }
    connect();
    return () => { if (wsRef.current) wsRef.current.close(); };
  }, []);

  const reset = useCallback(() => setProgress({ pct: 0, message: '' }), []);
  return { progress, reset };
}
