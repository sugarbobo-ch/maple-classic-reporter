import { AppConfig, ReportSubmissionMode } from '../../types';
import { RadioGroup, Switch } from '../ui';

interface ReportTabProps {
  config: AppConfig;
  onUpdateConfig: (key: keyof AppConfig, value: unknown) => void;
}

export default function ReportTab({ config, onUpdateConfig }: ReportTabProps) {
  const mode: ReportSubmissionMode =
    config.report_submission_mode === 'manual' ? 'manual' : 'automatic';

  return (
    <div className="report-settings-tab">
      <div className="settings-section-intro report-settings-intro">
        <div>
          <h2>檢舉方式</h2>
          <p>選擇預設的檢舉方式。送出前仍可更改。</p>
        </div>
      </div>

      <RadioGroup<ReportSubmissionMode>
        name="default-report-mode"
        value={mode}
        direction="vertical"
        className="settings-choice-list settings-choice-list-2"
        onChange={(value) => onUpdateConfig('report_submission_mode', value)}
        options={[
          {
            value: 'automatic',
            label: (
              <span className="settings-choice-copy">
                <strong>自動檢舉</strong><small>使用獨立的 Chromium 瀏覽器環境填寫官方表單。</small>
              </span>
            ),
          },
          {
            value: 'manual',
            label: (
              <span className="settings-choice-copy">
                <strong>手動檢舉</strong><small>上傳證據後，由你開啟官方頁面並複製欄位。</small>
              </span>
            ),
          },
        ]}
      />

      {mode === 'automatic' && (
        <div className="report-settings-background-setting">
          <div className="setting-info">
            <span className="setting-label">在背景完成填表</span>
            <span className="setting-desc">
              開啟後不顯示瀏覽器視窗；關閉後可看到填表與送出過程。
            </span>
          </div>
          <Switch
            checked={config.form_submit_headless !== false}
            onChange={(value) => onUpdateConfig('form_submit_headless', value)}
            aria-label="在背景完成填表"
          />
        </div>
      )}
    </div>
  );
}
