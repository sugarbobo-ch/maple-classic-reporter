import { Trash2, CheckCircle, Info } from 'lucide-react';
import { Dialog, Button } from '../ui';
import { ClearRecordingsResponse } from '../../types';

export interface ClearRecordingsModalProps {
  isOpen: boolean;
  clearResult: ClearRecordingsResponse | null;
  clearingProgress: boolean;
  onClose: () => void;
  onExecuteClear: () => void;
}

export default function ClearRecordingsModal({
  isOpen,
  clearResult,
  clearingProgress,
  onClose,
  onExecuteClear,
}: ClearRecordingsModalProps) {
  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="清理本機暫存錄影"
      titleIcon={Trash2}
      maxWidth="420px"
      footer={
        clearResult ? (
          <Button variant="primary" size="md" onClick={onClose}>
            完成
          </Button>
        ) : (
          <>
            <Button variant="outline" size="md" onClick={onClose}>
              取消
            </Button>
            <Button
              variant="danger"
              size="md"
              onClick={onExecuteClear}
              disabled={clearingProgress}
            >
              {clearingProgress ? '清理中...' : '確認清理'}
            </Button>
          </>
        )
      }
    >
      {clearResult ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '6px 0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-status-success)', fontWeight: 600 }}>
            <CheckCircle size={20} />
            <span>清理完成！</span>
          </div>
          <div style={{ fontSize: '0.86rem', color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
            已成功刪除 <strong>{clearResult.count}</strong> 個本機暫存檔案，共釋放 <strong>{clearResult.size_str || '0 MB'}</strong> 容量。
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '6px 0' }}>
          <div style={{ fontSize: '0.88rem', color: 'var(--color-text)', lineHeight: 1.6 }}>
            確定要清理所有已錄製但尚未刪除的本機暫存影音檔案嗎？
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
            <Info size={14} />
            <span>此操作不會影響已上傳至 Google Drive 或送出的檢舉歷史紀錄。</span>
          </div>
        </div>
      )}
    </Dialog>
  );
}
