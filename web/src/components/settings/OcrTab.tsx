import { AlertCircle } from 'lucide-react';
import { Switch } from '../ui';
import { AppConfig } from '../../types';
import SettingRow from './SettingRow';

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
      <SettingRow
        label="角色 ID 自動 OCR 辨識"
        description="自動辨識遊戲畫面中的玩家名稱並提供候選名單"
      >
        <Switch
          checked={config.ocr_autofill_id !== false}
          onChange={() => handleToggle('ocr_autofill_id')}
        />
      </SettingRow>

      <SettingRow
        label="地圖名稱自動 OCR 辨識"
        description="自動辨識左上角小地圖區域文字並比對地圖目錄"
      >
        <Switch
          checked={config.ocr_autofill_map !== false}
          onChange={() => handleToggle('ocr_autofill_map')}
        />
      </SettingRow>

      <div className="settings-info-callout">
        <div className="settings-info-callout-title">
          <AlertCircle size={15} aria-hidden="true" />
          OCR 辨識說明
        </div>
        <p>
          RapidOCR 會在本機處理遊戲畫面，不會將畫面上傳至第三方辨識服務。
        </p>
      </div>
    </>
  );
}
