const MIN_CONTENT_SCALE = 0.25;
const MAX_CONTENT_SCALE = 4;

export function calculateWindowContentScale(
  initialDevicePixelRatio: number,
  currentDevicePixelRatio: number,
): number {
  if (
    !Number.isFinite(initialDevicePixelRatio) ||
    !Number.isFinite(currentDevicePixelRatio) ||
    initialDevicePixelRatio <= 0 ||
    currentDevicePixelRatio <= 0
  ) {
    return 1;
  }

  const scale = initialDevicePixelRatio / currentDevicePixelRatio;
  return Math.min(MAX_CONTENT_SCALE, Math.max(MIN_CONTENT_SCALE, scale));
}

export function installWindowScaleLock(): () => void {
  const root = document.documentElement;
  const content = document.getElementById('root');
  if (!content) {
    return () => undefined;
  }

  const initialDevicePixelRatio = window.devicePixelRatio || 1;
  let frameId: number | null = null;
  let lastScale = 1;

  const syncScale = () => {
    if (frameId !== null) {
      return;
    }

    frameId = window.requestAnimationFrame(() => {
      frameId = null;
      const scale = calculateWindowContentScale(
        initialDevicePixelRatio,
        window.devicePixelRatio || 1,
      );
      if (Math.abs(scale - lastScale) < 0.001) {
        return;
      }

      lastScale = scale;
      root.style.setProperty('--window-content-scale', String(scale));
    });
  };

  window.addEventListener('resize', syncScale, { passive: true });
  window.visualViewport?.addEventListener('resize', syncScale, { passive: true });
  syncScale();

  return () => {
    window.removeEventListener('resize', syncScale);
    window.visualViewport?.removeEventListener('resize', syncScale);
    if (frameId !== null) {
      window.cancelAnimationFrame(frameId);
    }
  };
}
