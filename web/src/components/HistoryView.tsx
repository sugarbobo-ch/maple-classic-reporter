import { useState } from 'react';
import {
  ArrowLeft,
  ExternalLink,
  Trash2,
  Check,
  Copy,
  ShieldAlert,
  ShieldCheck,
  RefreshCw,
  Clock,
  LayoutList,
  Rows,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react';
import { Button, IconButton, Badge, Tooltip, Dialog, Dropdown } from './ui';
import { useClipboard, useToast } from '../hooks';
import { HistoryRecord, SanctionSyncStatus } from '../types';

export interface HistoryViewProps {
  history?: HistoryRecord[];
  onBack: () => void;
  onClearHistory?: () => Promise<boolean>;
  onOpenUrl: (url: string) => void;
  onCheckSanctions?: () => Promise<void>;
  isCheckingSanctions?: boolean;
  sanctionSyncStatus?: SanctionSyncStatus | null;
  lastCompleteSyncAt?: string | null;
}

function formatLastSyncTime(isoStr?: string | null): string {
  if (!isoStr || !isoStr.trim()) return '尚未完成檢查';
  // Parse YYYY-MM-DDTHH:mm or similar
  const match = isoStr.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
  if (match) {
    return `${match[1]} ${match[2]}`;
  }
  return isoStr.slice(0, 16).replace('T', ' ');
}

function getPageNumbers(current: number, total: number): (number | '...')[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const pages: (number | '...')[] = [];
  if (current <= 4) {
    for (let i = 1; i <= 5; i++) pages.push(i);
    pages.push('...');
    pages.push(total);
  } else if (current >= total - 3) {
    pages.push(1);
    pages.push('...');
    for (let i = total - 4; i <= total; i++) pages.push(i);
  } else {
    pages.push(1);
    pages.push('...');
    pages.push(current - 1);
    pages.push(current);
    pages.push(current + 1);
    pages.push('...');
    pages.push(total);
  }
  return pages;
}

export default function HistoryView({
  history = [],
  onBack,
  onClearHistory,
  onOpenUrl,
  onCheckSanctions,
  isCheckingSanctions = false,
  sanctionSyncStatus = null,
  lastCompleteSyncAt = null,
}: HistoryViewProps) {
  const { copy } = useClipboard();
  const { toast } = useToast();
  const [copiedUrl, setCopiedUrl] = useState('');
  const [isClearingHistory, setIsClearingHistory] = useState(false);
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [isCompact, setIsCompact] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);

  const totalRecords = history.length;
  const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));
  const safeCurrentPage = Math.min(Math.max(1, currentPage), totalPages);
  const startIndex = (safeCurrentPage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, totalRecords);
  const paginatedHistory = history.slice(startIndex, endIndex);

  const handleOpenClearConfirm = () => {
    setClearConfirmOpen(true);
  };

  const handleConfirmClear = async () => {
    if (!onClearHistory || isClearingHistory) return;
    setIsClearingHistory(true);
    try {
      const ok = await onClearHistory();
      if (ok) {
        setClearConfirmOpen(false);
        setCurrentPage(1);
      }
    } finally {
      setIsClearingHistory(false);
    }
  };

  const handleCopyUrl = async (url: string) => {
    const copied = await copy(url);
    if (!copied) {
      toast.error('複製連結失敗', '請確認剪貼簿權限後重試。');
      return;
    }

    setCopiedUrl(url);
    toast.success('連結已複製');
    window.setTimeout(() => {
      setCopiedUrl((current) => (current === url ? '' : current));
    }, 2000);
  };

  const renderBanStatus = (row: HistoryRecord) => {
    const s = (row.ban_status || '').trim().toLowerCase();
    const isBanned = s === 'banned' || s === '已制裁' || s === '已封鎖' || Boolean(row.ban_date);
    const resultText = row.ban_result || '永久鎖定';
    const maskedName = row.ban_masked_name || '';
    const announcementUrl = (row.ban_announcement_url || '').trim();

    if (isBanned) {
      const tooltipMsg = maskedName
        ? `官方公告命中：${maskedName}（${resultText}）`
        : `制裁結果：${resultText}`;

      return (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <Tooltip content={tooltipMsg}>
            <Badge
              variant="danger"
              size="sm"
              icon={ShieldAlert}
              tabIndex={0}
              role="status"
              aria-label={`已制裁：${resultText}`}
            >
              已制裁
            </Badge>
          </Tooltip>
          {announcementUrl && (
            <IconButton
              icon={ExternalLink}
              size="sm"
              variant="ghost"
              tooltip="開啟官方制裁公告"
              aria-label="開啟官方制裁公告"
              onClick={() => onOpenUrl(announcementUrl)}
            />
          )}
        </div>
      );
    }

    if (s === 'unbanned' || s === '未被制裁' || s === '未封鎖') {
      return (
        <Badge variant="success" size="sm" icon={ShieldCheck}>
          未被制裁
        </Badge>
      );
    }

    if (s === 'investigating' || s === '審查中') {
      return (
        <Badge variant="warning" size="sm" icon={Clock}>
          審查中
        </Badge>
      );
    }

    return (
      <Badge variant="default" size="sm">
        {row.ban_status && row.ban_status !== 'pending' ? row.ban_status : '待檢查'}
      </Badge>
    );
  };

  const renderUploadStatus = (status?: string) => {
    const normalized = (status || '').trim().toLowerCase();
    if (!status || !normalized) {
      return <span style={{ color: 'var(--color-text-secondary)' }}>-</span>;
    }

    if (['成功', '模擬成功', 'success', 'uploaded'].includes(normalized)) {
      return (
        <Badge variant="success" size="sm" icon={Check}>
          {status}
        </Badge>
      );
    }

    if (['失敗', 'error', 'failed'].includes(normalized)) {
      return (
        <Badge variant="danger" size="sm" icon={ShieldAlert}>
          {status}
        </Badge>
      );
    }

    return (
      <Badge variant="default" size="sm">
        {status}
      </Badge>
    );
  };

  const formatBanDate = (dateStr?: string) => {
    if (!dateStr || dateStr.trim() === '') return '-';
    // Return only YYYY-MM-DD
    const match = dateStr.match(/^\d{4}-\d{2}-\d{2}/);
    if (match) return match[0];
    return dateStr.split(' ')[0] || '-';
  };

  const syncMessage = sanctionSyncStatus?.message || (
    sanctionSyncStatus?.phase === 'fetching' && sanctionSyncStatus?.current && sanctionSyncStatus?.total
      ? `正在檢查第 ${sanctionSyncStatus.current}/${sanctionSyncStatus.total} 篇公告`
      : '正在同步官方公告…'
  );

  return (
    <div
      className="card-section"
      style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}
    >
      <div className="modal-header" style={{ flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <IconButton
            icon={ArrowLeft}
            size="md"
            variant="ghost"
            tooltip="返回首頁"
            onClick={onBack}
          />
          <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--color-text-heading)' }}>
            回報紀錄
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <span
            style={{
              fontSize: '0.78rem',
              color: 'var(--color-text-secondary)',
            }}
          >
            上次完整檢查：{formatLastSyncTime(lastCompleteSyncAt || sanctionSyncStatus?.last_complete_sync_at)}
          </span>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Button
              variant={isCompact ? 'primary' : 'outline'}
              size="md"
              icon={isCompact ? Rows : LayoutList}
              onClick={() => setIsCompact((prev) => !prev)}
              title={isCompact ? '切換為標準排列' : '切換為緊密排列'}
              data-testid="toggle-compact-mode"
            >
              {isCompact ? '緊密排列' : '標準排列'}
            </Button>

            <Button
              variant="secondary"
              size="md"
              icon={RefreshCw}
              onClick={() => {
                if (onCheckSanctions && !isCheckingSanctions) {
                  void onCheckSanctions();
                }
              }}
              loading={isCheckingSanctions}
              disabled={isCheckingSanctions || !onCheckSanctions}
              aria-busy={isCheckingSanctions}
              data-testid="check-sanction-status"
            >
              {isCheckingSanctions ? '檢查中…' : '檢查制裁狀態'}
            </Button>
          </div>

          {history.length > 0 && (
            <Button
              variant="ghost"
              size="md"
              icon={Trash2}
              onClick={handleOpenClearConfirm}
              loading={isClearingHistory}
              disabled={!onClearHistory || isCheckingSanctions}
              aria-busy={isClearingHistory}
              data-testid="clear-history"
            >
              清空紀錄
            </Button>
          )}
        </div>
      </div>

      {/* Sanction Sync Diagnostics Banner */}
      <div
        style={{
          padding: '8px 16px',
          backgroundColor: isCheckingSanctions ? 'var(--color-primary-light)' : 'var(--color-surface)',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '10px',
          fontSize: '0.78rem',
          color: 'var(--color-text-secondary)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, color: 'var(--color-text-heading)', display: 'flex', alignItems: 'center', gap: '4px' }}>
            官方懲處公告診斷：
          </span>
          {isCheckingSanctions ? (
            <span style={{ color: 'var(--color-primary)', fontWeight: 600 }}>
              {syncMessage}
            </span>
          ) : (
            <span>
              已對齊 Beanfun 官方制裁公告庫，共 <strong>{history.length}</strong> 筆紀錄（
              <strong style={{ color: 'var(--color-danger)' }}>
                {history.filter((h) => (h.ban_status || '').toLowerCase() === 'banned' || Boolean(h.ban_date)).length} 筆已制裁
              </strong>
              ，
              <strong style={{ color: 'var(--color-status-success)' }}>
                {history.filter((h) => (h.ban_status || '').toLowerCase() === 'unbanned' && !h.ban_date).length} 筆未命中
              </strong>
              ）
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <a
            href="https://maplestoryclassic.beanfun.com/main?section=mBulletin&kind=758"
            target="_blank"
            rel="noreferrer"
            onClick={(e) => {
              e.preventDefault();
              onOpenUrl('https://maplestoryclassic.beanfun.com/main?section=mBulletin&kind=758');
            }}
            style={{
              color: 'var(--color-primary)',
              textDecoration: 'none',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              fontWeight: 500,
            }}
          >
            開啟官方懲處公告網頁
            <ExternalLink size={12} />
          </a>
        </div>
      </div>

      <div className="history-table-container" style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        {history.length > 0 ? (
          <table className={`history-table ${isCompact ? 'compact' : ''}`.trim()}>
            <thead>
              <tr>
                <th>檢舉時間</th>
                <th>嫌疑人 ID</th>
                <th>伺服器</th>
                <th>所在地圖</th>
                <th>上傳狀態</th>
                <th>制裁狀態</th>
                <th>制裁時間</th>
                <th style={{ textAlign: 'center' }}>事證連結</th>
              </tr>
            </thead>
            <tbody>
              {paginatedHistory.map((row, idx) => {
                const key = row.record_id || `history-${row.timestamp || row.time || 'item'}-${row.suspect_id || row.id || idx}-${idx}`;
                const evidenceUrl = (row.evidence_url || row.url || '').trim();
                const isCopied = copiedUrl === evidenceUrl;

                return (
                  <tr key={key}>
                    <td className="cell-date">
                      {row.timestamp || row.time || '-'}
                    </td>
                    <td className="cell-suspect">
                      {row.suspect_id || row.id || '-'}
                    </td>
                    <td className="cell-nowrap">{row.server || '-'}</td>
                    <td>{row.map_name || row.map || '-'}</td>
                    <td className="cell-nowrap">
                      {renderUploadStatus(row.upload_status || row.status)}
                    </td>
                    <td className="cell-nowrap">
                      {renderBanStatus(row)}
                    </td>
                    <td className="cell-date">
                      {formatBanDate(row.ban_date)}
                    </td>
                    <td className="cell-nowrap" style={{ textAlign: 'center' }}>
                      {evidenceUrl ? (
                        <div className="history-actions">
                          <Button
                            variant="outline"
                            size="sm"
                            icon={ExternalLink}
                            onClick={() => onOpenUrl(evidenceUrl)}
                            title="開啟雲端事證連結"
                            aria-label="開啟雲端事證連結"
                          >
                            開啟連結
                          </Button>
                          <Button
                            variant={isCopied ? 'success' : 'secondary'}
                            size="sm"
                            icon={isCopied ? Check : Copy}
                            onClick={() => void handleCopyUrl(evidenceUrl)}
                            title="複製雲端事證連結"
                            aria-label="複製雲端事證連結"
                            style={{ minWidth: '84px', justifyContent: 'center' }}
                          >
                            {isCopied ? '已複製' : '複製連結'}
                          </Button>
                        </div>
                      ) : (
                        <span style={{ color: 'var(--color-text-secondary)', fontSize: '0.8rem' }}>
                          無雲端連結
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div
            style={{
              textAlign: 'center',
              padding: '40px',
              color: 'var(--color-text-secondary)',
              fontSize: '0.9rem',
            }}
          >
            目前尚無歷史檢舉紀錄
          </div>
        )}
      </div>

      {/* Pagination Footer */}
      {totalRecords > 0 && (
        <div className="history-pagination-bar">
          <div className="history-pagination-info" data-testid="pagination-info">
            <span>
              顯示第 <strong>{startIndex + 1}</strong> ~ <strong>{endIndex}</strong> 筆，共{' '}
              <strong>{totalRecords}</strong> 筆紀錄
            </span>
          </div>

          <div className="history-pagination-controls">
            <div style={{ width: '110px' }}>
              <Dropdown<number>
                options={[
                  { value: 10, label: '10 筆 / 頁' },
                  { value: 15, label: '15 筆 / 頁' },
                  { value: 30, label: '30 筆 / 頁' },
                  { value: 50, label: '50 筆 / 頁' },
                  { value: 100, label: '100 筆 / 頁' },
                ]}
                value={pageSize}
                onChange={(val) => {
                  setPageSize(val);
                  setCurrentPage(1);
                }}
              />
            </div>

            <button
              type="button"
              className="pagination-page-btn"
              disabled={safeCurrentPage <= 1}
              onClick={() => setCurrentPage(1)}
              title="第一頁"
              aria-label="第一頁"
            >
              <ChevronsLeft size={14} />
            </button>

            <button
              type="button"
              className="pagination-page-btn"
              disabled={safeCurrentPage <= 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              title="上一頁"
              aria-label="上一頁"
            >
              <ChevronLeft size={14} />
            </button>

            {getPageNumbers(safeCurrentPage, totalPages).map((p, i) =>
              p === '...' ? (
                <span
                  key={`ellipsis-${i}`}
                  style={{ padding: '0 4px', color: 'var(--color-text-secondary)' }}
                >
                  …
                </span>
              ) : (
                <button
                  key={`page-${p}`}
                  type="button"
                  className={`pagination-page-btn ${p === safeCurrentPage ? 'active' : ''}`}
                  onClick={() => setCurrentPage(p)}
                  aria-label={`第 ${p} 頁`}
                  aria-current={p === safeCurrentPage ? 'page' : undefined}
                >
                  {p}
                </button>
              )
            )}

            <button
              type="button"
              className="pagination-page-btn"
              disabled={safeCurrentPage >= totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              title="下一頁"
              aria-label="下一頁"
            >
              <ChevronRight size={14} />
            </button>

            <button
              type="button"
              className="pagination-page-btn"
              disabled={safeCurrentPage >= totalPages}
              onClick={() => setCurrentPage(totalPages)}
              title="最後一頁"
              aria-label="最後一頁"
            >
              <ChevronsRight size={14} />
            </button>
          </div>
        </div>
      )}

      {clearConfirmOpen && (
        <Dialog
          isOpen={true}
          onClose={isClearingHistory ? undefined : () => setClearConfirmOpen(false)}
          title="清空歷史紀錄"
          titleIcon={Trash2}
          maxWidth="440px"
          footer={
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', width: '100%' }}>
              <Button
                variant="outline"
                size="md"
                onClick={() => setClearConfirmOpen(false)}
                disabled={isClearingHistory}
              >
                取消
              </Button>
              <Button
                variant="primary"
                size="md"
                onClick={handleConfirmClear}
                loading={isClearingHistory}
                disabled={isClearingHistory}
                style={{ backgroundColor: 'var(--color-status-danger, #ef5350)' }}
                data-testid="confirm-clear-history-button"
              >
                確定清空
              </Button>
            </div>
          }
        >
          <div style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem', lineHeight: '1.5' }}>
            確定要清空本機的所有檢舉歷史紀錄嗎？
            <div style={{ marginTop: '8px', color: 'var(--color-status-danger, #ef5350)', fontSize: '0.85rem' }}>
              ⚠️ 此操作將永久刪除本地紀錄，無法復原。
            </div>
          </div>
        </Dialog>
      )}
    </div>
  );
}
