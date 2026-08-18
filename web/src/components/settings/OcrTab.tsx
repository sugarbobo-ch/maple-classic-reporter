import { Switch } from '../ui';
import { AppConfig } from '../../types';

export interface OcrTabProps {
  config: AppConfig;
  onUpdateConfig: (key: keyof AppConfig, value: unknown) => void;
}

export default function OcrTab({ config, onUpdateConfig }: OcrTabProps) {
  const handleToggle = (key: keyof AppConfig) => {
    onUpdateConfig(key, !config[key]);
  };

  return (
    <>
      <div className="setting-row">
        <div className="setting-info">
          <span className="setting-label">角色 ID 自動 OCR 辨識</span>
          <span className="setting-desc">自動辨識遊戲畫面中之玩家名稱並提供候選名單</span>
        </div>
        <Switch
          checked={config.ocr_autofill_id !== false}
          onChange={() => handleToggle('ocr_autofill_id')}
        />
      </div>

      <div className="setting-row">
        <div className="setting-info">
          <span className="setting-label">地圖名稱自動 OCR 辨識</span>
          <span className="setting-desc">自動辨識左上角小地圖區域文字並比對地圖目錄</span>
        </div>
        <Switch
          checked={config.ocr_autofill_map !== false}
          onChange={() => handleToggle('ocr_autofill_map')}
        />
      </div>

      <div
        style={{
          padding: '12px 16px',
          backgroundColor: 'var(--color-surface-card)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-md)',
          fontSize: '0.82rem',
          lineHeight: 1.6,
          color: 'var(--color-text-secondary)',
          marginTop: '4px',
        }}
      >
        <div style={{ fontWeight: 700, color: 'var(--color-text-heading)', marginBottom: '4px' }}>
          OCR 引擎架構說明：
        </div>
        採用 RapidOCR (ONNX Runtime) 本地快速模型搭配 Windows 內建 OCR 引擎，並結合小地圖專用前處理與模糊比對庫，可精準識別「地區、村莊、隱密之地」等複雜地圖名稱。
      </div>
    </>
  );
}
