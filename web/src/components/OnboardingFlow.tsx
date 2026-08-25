import { useEffect, useRef, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  Check,
  ChevronDown,
  ChevronUp,
  CloudUpload,
  Eye,
  History,
  ScanText,
  ScreenShare,
  ShieldCheck,
  Video,
} from 'lucide-react';
import {
  AppConfig,
  AudioCaptureMode,
  ReportSubmissionMode,
  UploadDestination,
  WindowItem,
} from '../types';
import { Button, Dropdown, Input, RadioGroup, Switch } from './ui';
import { getReporterBridge } from '../bridge/reporterBridge';

interface OnboardingFlowProps {
  config: AppConfig;
  windows: WindowItem[];
  gdriveAuthenticated: boolean | null;
  gdriveAuthLoading?: boolean;
  onUpdateConfig: (key: keyof AppConfig, value: unknown) => void;
  onUpdateConfigBatch: (updates: Partial<AppConfig>) => void;
  onAuthenticateDrive: () => void | Promise<void>;
  onFinish: () => void | Promise<void>;
  onSkip: () => void | Promise<void>;
}

const SETUP_STEPS = ['認識流程', '錄影', '辨識', '上傳', '檢舉', '完成'];
const PIPELINE = [
  { label: '蒐證', icon: Video },
  { label: '辨識', icon: ScanText },
  { label: '上傳', icon: CloudUpload },
  { label: '檢舉', icon: ShieldCheck },
  { label: '回顧', icon: History },
];

export default function OnboardingFlow({
  config,
  windows,
  gdriveAuthenticated,
  gdriveAuthLoading = false,
  onUpdateConfig,
  onUpdateConfigBatch,
  onAuthenticateDrive,
  onFinish,
  onSkip,
}: OnboardingFlowProps) {
  const [step, setStep] = useState(0);
  const [advancedRecording, setAdvancedRecording] = useState(false);
  const [discordTestState, setDiscordTestState] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
  const [discordTestMessage, setDiscordTestMessage] = useState('');
  const headingRef = useRef<HTMLHeadingElement>(null);
  const contentRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (contentRef.current) contentRef.current.scrollTop = 0;
    headingRef.current?.focus({ preventScroll: true });
  }, [step]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', config.theme === 'dark' ? 'dark' : 'light');
  }, [config.theme]);

  const reportMode: ReportSubmissionMode =
    config.report_submission_mode === 'manual' ? 'manual' : 'automatic';
  const audioMode: AudioCaptureMode =
    config.audio_capture_mode || (config.record_audio === false ? 'off' : 'process');

  const applyRecordingPreset = (preset: string) => {
    const values =
      preset === 'smooth'
        ? { recording_preset: 'smooth' as const, record_duration_sec: 10, record_fps: 30, replay_buffer_sec: 30 }
        : preset === 'ultra_fast'
          ? { recording_preset: 'ultra_fast' as const, record_duration_sec: 6, record_fps: 15, replay_buffer_sec: 15 }
          : { recording_preset: 'balanced' as const, record_duration_sec: 8, record_fps: 20, replay_buffer_sec: 20 };
    onUpdateConfigBatch(values);
  };

  const testDiscord = async () => {
    const webhook = config.discord_webhook_url.trim();
    if (!webhook) {
      setDiscordTestState('error');
      setDiscordTestMessage('請先貼上 Discord Webhook 網址。');
      return;
    }
    const bridge = getReporterBridge();
    if (!bridge) {
      setDiscordTestState('success');
      setDiscordTestMessage('預覽模式已略過連線測試。');
      return;
    }
    setDiscordTestState('testing');
    const result = await bridge.integrations.testDiscordWebhook(webhook);
    setDiscordTestState(result.success ? 'success' : 'error');
    setDiscordTestMessage(result.message);
  };

  const next = () => setStep((current) => Math.min(SETUP_STEPS.length - 1, current + 1));
  const back = () => setStep((current) => Math.max(0, current - 1));

  return (
    <main className="onboarding-shell" aria-label="首次使用設定">
      <div className="onboarding-progress" aria-label="設定進度">
        {SETUP_STEPS.map((label, index) => (
          <div
            key={label}
            className={`onboarding-progress-item ${index === step ? 'active' : ''} ${index < step ? 'complete' : ''}`.trim()}
            aria-current={index === step ? 'step' : undefined}
          >
            <span>{index < step ? <Check size={14} /> : index + 1}</span>
            <small>{label}</small>
          </div>
        ))}
      </div>

      <section ref={contentRef} className="onboarding-content onboarding-scroll-region" aria-live="polite">
        {step === 0 && (
          <div className="onboarding-welcome">
            <div className="onboarding-welcome-copy">
              <h1
                ref={headingRef}
                tabIndex={-1}
                aria-label="新楓之谷：經典版《自動外掛檢舉工具》"
              >
                <span className="onboarding-title-line">新楓之谷：經典版</span>
                <span className="onboarding-title-line">《自動外掛檢舉工具》</span>
              </h1>
              <p>協助你錄影蒐證、辨識角色資訊、上傳證據，並選擇手動或自動完成官方檢舉。</p>
              <div className="onboarding-primary-actions">
                <Button variant="primary" size="lg" icon={ArrowRight} iconPosition="right" onClick={next}>
                  開始設定
                </Button>
                <Button variant="ghost" size="lg" onClick={onSkip}>使用預設設定</Button>
              </div>
            </div>

            <div className="workflow-preview" aria-label="外掛檢舉流程">
              {PIPELINE.map(({ label, icon: Icon }, index) => (
                <div className="workflow-preview-step" key={label}>
                  <span><Icon size={22} strokeWidth={1.8} /></span>
                  <strong>{label}</strong>
                  {index < PIPELINE.length - 1 && <ArrowRight size={16} aria-hidden="true" />}
                </div>
              ))}
            </div>

            <div className="onboarding-technology">
              <div><span className="onboarding-technology-icon"><ScreenShare size={20} /></span><span>只擷取你指定的遊戲視窗，不會錄到其他視窗。</span></div>
              <div><span className="onboarding-technology-icon"><ScanText size={20} /></span><span>從畫面辨識角色 ID 與地圖文字。</span></div>
              <div><span className="onboarding-technology-icon"><Eye size={20} /></span><span>不讀取、不修改任何遊戲記憶體。</span></div>
              <div><span className="onboarding-technology-icon"><CloudUpload size={20} /></span><span>協助上傳證據並設定可檢視權限。</span></div>
              <div><span className="onboarding-technology-icon"><Bot size={20} /></span><span>自動模式會在獨立的瀏覽器環境填寫檢舉表單。</span></div>
              <div><span className="onboarding-technology-icon"><History size={20} /></span><span>回報紀錄會追蹤送件與官方處分結果。</span></div>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="onboarding-step-panel">
            <h1 ref={headingRef} tabIndex={-1}>錄影</h1>
            <p>先選擇遊戲視窗與適合電腦效能的品質。</p>
            <label className="onboarding-field-label">目標遊戲視窗</label>
            <Dropdown<string>
              options={windows.map((item) => ({ value: item.title, label: item.title }))}
              value={config.selected_window_title}
              onChange={(value) => onUpdateConfig('selected_window_title', value)}
            />
            <label className="onboarding-field-label">錄影品質</label>
            <RadioGroup<string>
              name="recording-quality"
              value={config.recording_preset || 'balanced'}
              onChange={applyRecordingPreset}
              direction="vertical"
              className="onboarding-radio-list onboarding-radio-list-3"
              itemClassName="onboarding-radio-card"
              options={[
                {
                  value: 'ultra_fast',
                  label: <span className="onboarding-radio-copy"><strong>省效能</strong><small>降低 FPS 與片段長度，適合較舊的電腦。</small></span>,
                },
                {
                  value: 'balanced',
                  label: <span className="onboarding-radio-copy"><strong>平衡（建議）</strong><small>兼顧辨識畫質、錄影流暢度與系統負擔。</small></span>,
                },
                {
                  value: 'smooth',
                  label: <span className="onboarding-radio-copy"><strong>較流暢</strong><small>使用較高 FPS，適合效能充足的電腦。</small></span>,
                },
              ]}
            />
            <button
              type="button"
              className="onboarding-disclosure"
              onClick={() => setAdvancedRecording((current) => !current)}
              aria-expanded={advancedRecording}
            >
              進階設定 {advancedRecording ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
            {advancedRecording && (
              <div className="onboarding-advanced-grid">
                <Input
                  label="錄影秒數"
                  type="number"
                  min="1"
                  max="60"
                  value={String(config.record_duration_sec)}
                  onChange={(event) => onUpdateConfig('record_duration_sec', Number(event.target.value) || 8)}
                />
                <Dropdown<number>
                  label="每秒畫面數"
                  options={[15, 20, 30, 60].map((value) => ({ value, label: `${value} FPS` }))}
                  value={config.record_fps}
                  onChange={(value) => onUpdateConfig('record_fps', value)}
                />
                <Dropdown<number>
                  label="錄影前倒數"
                  options={[0, 3, 5].map((value) => ({ value, label: value === 0 ? '不倒數' : `${value} 秒` }))}
                  value={config.record_countdown_sec || 0}
                  onChange={(value) => onUpdateConfig('record_countdown_sec', value)}
                />
                <Dropdown<AudioCaptureMode>
                  label="錄音來源"
                  options={[
                    { value: 'process', label: '僅遊戲聲音' },
                    { value: 'system', label: '所有系統聲音' },
                    { value: 'off', label: '不錄音' },
                  ]}
                  value={audioMode}
                  onChange={(value) => onUpdateConfig('audio_capture_mode', value)}
                />
              </div>
            )}
          </div>
        )}

        {step === 2 && (
          <div className="onboarding-step-panel">
            <h1 ref={headingRef} tabIndex={-1}>辨識</h1>
            <p>辨識會分析截圖和影片中的畫面，找出角色 ID 與地圖文字。不會讀取或修改遊戲程序或記憶體。</p>
            <div className="onboarding-setting-row">
              <div><strong>角色 ID 辨識</strong><span>從畫面找出疑似外掛角色名稱。</span></div>
              <Switch checked={config.ocr_autofill_id !== false} onChange={(value) => onUpdateConfig('ocr_autofill_id', value)} />
            </div>
            <div className="onboarding-setting-row">
              <div><strong>地圖名稱辨識</strong><span>優先辨識遊戲視窗左上角的小地圖文字。</span></div>
              <Switch checked={config.ocr_autofill_map !== false} onChange={(value) => onUpdateConfig('ocr_autofill_map', value)} />
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="onboarding-step-panel">
            <h1 ref={headingRef} tabIndex={-1}>上傳</h1>
            <p>選擇證據要存放的位置，也可以先體驗錄影與辨識，不上傳任何檔案。</p>
            <RadioGroup<UploadDestination>
              name="upload-destination"
              direction="vertical"
              value={config.upload_destination}
              onChange={(value) => onUpdateConfig('upload_destination', value)}
              className="onboarding-radio-list onboarding-radio-list-3"
              itemClassName="onboarding-radio-card"
              options={[
                {
                  value: 'gdrive',
                  label: <span className="onboarding-radio-copy"><strong>Google Drive（建議）</strong><small>適合長期保存高畫質影片，並建立可檢視的證據連結。</small></span>,
                },
                {
                  value: 'discord',
                  label: <span className="onboarding-radio-copy"><strong>Discord Webhook</strong><small>適合快速分享短片，檔案大小受 Discord 限制。</small></span>,
                },
                {
                  value: 'none',
                  label: <span className="onboarding-radio-copy"><strong>只在本機試用</strong><small>不連接雲端，也不會上傳任何影片或圖片。</small></span>,
                },
              ]}
            />
            {config.upload_destination === 'gdrive' && (
              <div className="onboarding-upload-details onboarding-connection-row">
                <span>{gdriveAuthenticated ? 'Google Drive 已連線' : '尚未連線 Google Drive'}</span>
                <Button variant={gdriveAuthenticated ? 'success' : 'primary'} size="md" loading={gdriveAuthLoading} onClick={onAuthenticateDrive}>
                  {gdriveAuthenticated ? '重新認證' : '連線 Google Drive'}
                </Button>
              </div>
            )}
            {config.upload_destination === 'discord' && (
              <div className="onboarding-upload-details">
                <div className="discord-webhook-guide">
                  <strong>如何建立 Discord Webhook</strong>
                  <ol>
                    <li>在 Discord 伺服器建立一個專用文字頻道。</li>
                    <li>開啟「編輯頻道」，前往「整合」，選擇「Webhook」並新增 Webhook。</li>
                    <li>複製 Webhook 網址，貼到下方後測試連線。</li>
                  </ol>
                  <small>Webhook 網址具有上傳權限，請勿分享給其他人。</small>
                </div>
                <div className="onboarding-discord-fields">
                  <Input
                    label="Discord Webhook 網址"
                    type="password"
                    placeholder="https://discord.com/api/webhooks/..."
                    value={config.discord_webhook_url}
                    onChange={(event) => {
                      onUpdateConfig('discord_webhook_url', event.target.value);
                      setDiscordTestState('idle');
                    }}
                  />
                  <Button variant="secondary" size="md" onClick={testDiscord} loading={discordTestState === 'testing'}>測試連線</Button>
                  {discordTestMessage && <p className={`connection-feedback ${discordTestState}`} role="status">{discordTestMessage}</p>}
                </div>
              </div>
            )}
            {config.upload_destination !== 'none' && (
              <div className="onboarding-setting-row">
                <div><strong>完成檢舉後刪除本機證據</strong><span>只有確認檢舉成功後才清理程式產生的檔案。</span></div>
                <Switch checked={config.auto_delete_after_upload} onChange={(value) => onUpdateConfig('auto_delete_after_upload', value)} />
              </div>
            )}
            {config.upload_destination === 'none' && (
              <div className="onboarding-trial-note" role="status">
                <div><strong>只試用模式</strong><span>你可以體驗蒐證與辨識；送出檢舉前必須回到設定選擇 Google Drive 或 Discord。</span></div>
              </div>
            )}
          </div>
        )}

        {step === 4 && (
          <div className="onboarding-step-panel">
            <h1 ref={headingRef} tabIndex={-1}>檢舉方式</h1>
            <p>選擇手動填寫或由工具自動填寫。</p>
            <RadioGroup<ReportSubmissionMode>
              name="report-mode"
              direction="vertical"
              value={reportMode}
              onChange={(value) => onUpdateConfig('report_submission_mode', value)}
              className="onboarding-radio-list onboarding-radio-list-2"
              itemClassName="onboarding-radio-card"
              options={[
                { value: 'automatic', label: <span className="onboarding-radio-copy"><strong>自動檢舉</strong><small>使用獨立瀏覽器環境填寫並送出官方表單。</small></span> },
                { value: 'manual', label: <span className="onboarding-radio-copy"><strong>手動檢舉</strong><small>上傳後開啟官方頁面，逐欄複製資料。</small></span> },
              ]}
            />
            {reportMode === 'automatic' && (
              <div className="onboarding-setting-row">
                <div><strong>在背景完成填表</strong><span>開啟後不顯示瀏覽器；關閉後會顯示填表與送出過程。</span></div>
                <Switch checked={config.form_submit_headless !== false} onChange={(value) => onUpdateConfig('form_submit_headless', value)} />
              </div>
            )}
          </div>
        )}

        {step === 5 && (
          <div className="onboarding-summary">
            <div className="onboarding-summary-main">
              <span className="onboarding-summary-icon"><Check size={30} /></span>
              <h1 ref={headingRef} tabIndex={-1}>設定完成</h1>
              <p>你已完成基本設定，之後仍可在偏好設定中調整。</p>
              <Button variant="primary" size="lg" icon={ArrowRight} iconPosition="right" onClick={onFinish}>開始使用</Button>
            </div>
            <div className="onboarding-summary-details">
              <h2>設定摘要</h2>
              <dl>
                <div><dt>錄影品質</dt><dd>{config.recording_preset === 'smooth' ? '較流暢' : config.recording_preset === 'ultra_fast' ? '省效能' : '平衡'}</dd></div>
                <div><dt>辨識</dt><dd>{config.ocr_autofill_id !== false || config.ocr_autofill_map !== false ? '已啟用' : '手動填寫'}</dd></div>
                <div><dt>上傳</dt><dd>{config.upload_destination === 'gdrive' ? 'Google Drive' : config.upload_destination === 'discord' ? 'Discord' : '不上傳'}</dd></div>
                <div><dt>檢舉方式</dt><dd>{reportMode === 'automatic' ? '自動檢舉' : '手動檢舉'}</dd></div>
              </dl>
            </div>
          </div>
        )}
      </section>

      {step > 0 && step < SETUP_STEPS.length - 1 && (
        <footer className="onboarding-footer">
          <Button variant="ghost" size="md" icon={ArrowLeft} onClick={back}>上一步</Button>
          <Button variant="primary" size="md" icon={ArrowRight} iconPosition="right" onClick={next}>下一步</Button>
        </footer>
      )}
    </main>
  );
}
