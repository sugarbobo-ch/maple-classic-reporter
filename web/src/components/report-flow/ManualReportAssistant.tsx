import { useState } from 'react';
import { Check, Copy, ExternalLink } from 'lucide-react';
import { Button } from '../ui';
import { useClipboard, useToast } from '../../hooks';
import { HistoryRecord } from '../../types';

interface ManualReportAssistantProps {
  record: HistoryRecord;
  isConfirming?: boolean;
  onOpenReportPage: () => void;
  onConfirm: (recordId: string) => void | Promise<void>;
  onLater: () => void;
}

const COPY_FIELDS: Array<{
  key: string;
  label: string;
  value: (record: HistoryRecord) => string;
  copyable: boolean;
}> = [
  { key: 'suspect', label: '角色 ID', value: (record) => record.suspect_id || record.id || '', copyable: true },
  { key: 'server', label: '伺服器', value: (record) => record.server || '', copyable: false },
  { key: 'map', label: '地圖名稱', value: (record) => record.map_name || record.map || '', copyable: true },
  { key: 'note', label: '違規說明', value: (record) => record.note || '', copyable: true },
  {
    key: 'evidence',
    label: '檢舉證據網址',
    value: (record) => record.evidence_url || record.url || '',
    copyable: true,
  },
];

export default function ManualReportAssistant({
  record,
  isConfirming = false,
  onOpenReportPage,
  onConfirm,
  onLater,
}: ManualReportAssistantProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [copiedKey, setCopiedKey] = useState('');
  const { copy } = useClipboard();
  const { toast } = useToast();

  const handleCopy = async (key: string, value: string) => {
    if (!value) return;
    if (!(await copy(value))) {
      toast.error('複製失敗', '請確認剪貼簿權限後重試。');
      return;
    }
    setCopiedKey(key);
    window.setTimeout(() => setCopiedKey((current) => (current === key ? '' : current)), 1800);
  };

  return (
    <div className="manual-report-assistant" data-testid="manual-report-assistant">
      <div className="manual-report-intro">
        <h2>證據已上傳，接著完成官方表單</h2>
        <p>請開啟外掛檢舉頁面，依照下方順序填寫。伺服器請直接在表單中選取。</p>
        <div className="manual-report-open-action">
          <span className="manual-report-field-order" aria-hidden="true">1</span>
          <Button variant="primary" size="lg" icon={ExternalLink} onClick={onOpenReportPage}>
            開啟外掛檢舉頁面
          </Button>
        </div>
      </div>

      <div className="manual-report-fields" aria-label="手動檢舉欄位">
        {COPY_FIELDS.map((field, index) => {
          const value = field.value(record);
          const copied = copiedKey === field.key;
          return (
            <div className="manual-report-field" key={field.key}>
              <div className="manual-report-field-order" aria-hidden="true">{index + 2}</div>
              <div className="manual-report-field-content">
                <span>{field.label}</span>
                <strong>{value || '尚無資料'}</strong>
              </div>
              {field.copyable && (
                <Button
                  variant="secondary"
                  size="sm"
                  icon={copied ? Check : Copy}
                  onClick={() => handleCopy(field.key, value)}
                  disabled={!value}
                  aria-label={`複製${field.label}`}
                >
                  {copied ? '已複製' : '複製'}
                </Button>
              )}
            </div>
          );
        })}
      </div>

      {confirmOpen ? (
        <div className="manual-report-confirm" role="alert">
          <div>
            <strong>確認官方表單已送出成功？</strong>
            <p>完成確認後，這筆紀錄才會開始追蹤官方處分狀態。</p>
          </div>
          <div className="manual-report-confirm-actions">
            <Button variant="outline" size="md" onClick={() => setConfirmOpen(false)} disabled={isConfirming}>
              返回檢查
            </Button>
            <Button
              variant="success"
              size="md"
              loading={isConfirming}
              onClick={() => record.record_id && onConfirm(record.record_id)}
              disabled={!record.record_id || isConfirming}
            >
              確認已成功送出
            </Button>
          </div>
        </div>
      ) : (
        <div className="manual-report-actions">
          <Button variant="outline" size="md" onClick={onLater}>稍後完成</Button>
          <Button variant="success" size="md" icon={Check} onClick={() => setConfirmOpen(true)}>
            我已完成檢舉
          </Button>
        </div>
      )}
    </div>
  );
}
