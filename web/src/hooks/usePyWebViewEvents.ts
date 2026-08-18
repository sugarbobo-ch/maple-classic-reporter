import { useEffect } from 'react';
import { PyWebViewEvent, PyWebViewEventType } from '../types';

type EventHandler = (data: any) => void;

const listeners: Map<PyWebViewEventType, Set<EventHandler>> = new Map();

export function dispatchPyWebViewEvent(event: PyWebViewEvent) {
  if (!event || !event.type) return;
  const handlers = listeners.get(event.type);
  if (!handlers) return;

  handlers.forEach((fn) => {
    try {
      fn(event.data);
    } catch (e) {
      console.error('Error in PyWebView event handler:', e);
    }
  });
}

// Initialize global dispatcher once
if (typeof window !== 'undefined') {
  window.__MAPLE_REPORTER_EVENT__ = dispatchPyWebViewEvent;
}

export function usePyWebViewEvents(handlers: Partial<Record<PyWebViewEventType, EventHandler>>) {
  useEffect(() => {
    const entries = Object.entries(handlers) as [PyWebViewEventType, EventHandler][];
    entries.forEach(([type, fn]) => {
      if (!listeners.has(type)) {
        listeners.set(type, new Set());
      }
      listeners.get(type)!.add(fn);
    });

    return () => {
      entries.forEach(([type, fn]) => {
        const set = listeners.get(type);
        if (set) {
          set.delete(fn);
        }
      });
    };
  }, [handlers]);
}
