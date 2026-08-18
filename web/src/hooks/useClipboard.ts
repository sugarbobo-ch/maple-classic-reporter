import { useState, useCallback } from 'react';

export function useClipboard(timeout = 2000) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const copy = useCallback(
    async (text: string) => {
      try {
        // Desktop builds write through the native bridge first so copying does
        // not depend on WebView clipboard permissions.
        if (window.pywebview?.api?.set_clipboard_text) {
          const copiedByNative = await window.pywebview.api.set_clipboard_text(text);
          if (copiedByNative) {
            setCopied(true);
            setError(null);
            setTimeout(() => setCopied(false), timeout);
            return true;
          }
        }

        if (!navigator?.clipboard) {
          throw new Error('Clipboard API not available');
        }
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setError(null);
        setTimeout(() => setCopied(false), timeout);
        return true;
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Copy failed'));
        setCopied(false);
        return false;
      }
    },
    [timeout]
  );

  const read = useCallback(async () => {
    try {
      // Desktop builds read through the native bridge so WebView does not ask
      // for permission to inspect the browser clipboard.
      if (window.pywebview?.api?.get_clipboard_text) {
        const text = await window.pywebview.api.get_clipboard_text();
        setError(null);
        return text;
      }

      if (!navigator?.clipboard) {
        throw new Error('Clipboard API not available');
      }
      const text = await navigator.clipboard.readText();
      setError(null);
      return text;
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Read failed'));
      return '';
    }
  }, []);

  return { copied, error, copy, read };
}
