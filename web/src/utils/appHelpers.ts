import { WindowItem, AppConfig, OcrResultData } from '../types';

export const PREFERRED_WINDOW_TITLE = '新楓之谷：經典版';

export function choosePreferredWindow(windows: WindowItem[], savedTitle = ''): string {
  if (!windows || windows.length === 0) return PREFERRED_WINDOW_TITLE;

  // 1. Exact match for "新楓之谷：經典版"
  const exact = windows.find((window) => window.title.trim() === PREFERRED_WINDOW_TITLE);
  if (exact) return exact.title;

  // 2. Contains "新楓之谷：經典版"
  const containsClassic = windows.find((window) => window.title.includes(PREFERRED_WINDOW_TITLE));
  if (containsClassic) return containsClassic.title;

  // 3. Related "新楓之谷"
  const related = windows.find((window) => window.title.includes('新楓之谷'));
  if (related) return related.title;

  // 4. Related "MapleStory" / "Maple" (case-insensitive)
  const maple = windows.find((window) => window.title.toLowerCase().includes('maple'));
  if (maple) return maple.title;

  // 5. Previously saved title if still open
  const saved = windows.find((window) => window.title === savedTitle);
  if (saved) return saved.title;

  // 6. If saved title was Maple-related, preserve it even if temporarily not in scanned list
  if (
    savedTitle &&
    (savedTitle.includes('新楓之谷') || savedTitle.toLowerCase().includes('maple'))
  ) {
    return savedTitle;
  }

  // 7. First scanned window
  return windows[0].title;
}

export function normalizeOcrResult(
  data: Partial<OcrResultData>,
  previous: OcrResultData,
  config: Pick<AppConfig, 'default_map' | 'ocr_autofill_map'>
): OcrResultData {
  const source = data.map_name_source;
  const mapName = String(data.map_name || previous.map_name || config.default_map || '').trim();
  const explicitOcrMap = source === 'default' ? '' : String(data.ocr_map_name || '').trim();
  const legacyMapName = String(data.map_name || '').trim();
  const legacyOcrMap =
    source === 'ocr'
      ? legacyMapName
      : source === 'default'
        ? ''
        : config.ocr_autofill_map !== false && legacyMapName !== String(config.default_map || '').trim()
          ? legacyMapName
          : '';
  const ocrMapName = explicitOcrMap || legacyOcrMap;

  return {
    ...previous,
    ...data,
    suspect_ids:
      Array.isArray(data.suspect_ids)
        ? data.suspect_ids
        : previous.suspect_ids,
    map_name: mapName,
    ocr_map_name: ocrMapName,
    map_name_source: source || (ocrMapName ? 'ocr' : mapName ? 'default' : undefined),
    media_path: data.media_path || previous.media_path,
    media_type: data.media_type || previous.media_type,
  };
}
