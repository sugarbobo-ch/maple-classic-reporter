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
  FileText,
  ScanSearch,
  MoreHorizontal,
  Cloud,
  X,
  ListChecks,
} from 'lucide-react';
import { Button, IconButton, Badge, Tooltip, Dialog, Dropdown } from './ui';
import { useHistoryManagement } from '../hooks';
import {
  EvidenceCleanupResult,
  EvidenceCleanupTarget,
  HistoryDeleteResult,
  HistoryRecord,
  SanctionSyncStatus,
} from '../types';
import {
  getCleanupTargets,
  getHistoryRecordId,
  getSubmissionState,
  isPendingRecord,
  isSubmittedRecord,
  SUBMISSION_AWAITING_MANUAL,
  SUBMISSION_DRAFT,
} from '../domain/history';

export interface HistoryViewProps {
  history?: HistoryRecord[];
  compactLayout?: boolean;
  onUpdateCompactLayout?: (compact: boolean) => void;
  pageSize?: number;
  onUpdatePageSize?: (size: number) => void;
  onBack: () => void;
  onClearHistory?: () => Promise<boolean>;
  onCleanupEvidence?: (
    recordIds: string[],
    targets: EvidenceCleanupTarget[]
  ) => Promise<EvidenceCleanupResult>;
  onDeleteHistoryEntries?: (
    recordIds: string[],
    cleanupTargets?: EvidenceCleanupTarget[]
  ) => Promise<HistoryDeleteResult>;
  onOpenUrl: (url: string) => void;
  onCheckSanctions?: () => Promise<void>;
  isCheckingSanctions?: boolean;
  sanctionSyncStatus?: SanctionSyncStatus | null;
  lastCompleteSyncAt?: string | null;
  onContinueDraft?: (record: HistoryRecord, runRecognition: boolean) => void;
  onContinueManual?: (record: HistoryRecord) => void;
  ocrAutofillId?: boolean;
  ocrAutofillMap?: boolean;
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
  compactLayout,
  onUpdateCompactLayout,
  pageSize: propPageSize,
  onUpdatePageSize,
  onBack,
  onClearHistory,
  onCleanupEvidence,
  onDeleteHistoryEntries,
  onOpenUrl,
  onCheckSanctions,
  isCheckingSanctions = false,
  sanctionSyncStatus = null,
  lastCompleteSyncAt = null,
  onContinueDraft,
  onContinueManual,
  ocrAutofillId = true,
  ocrAutofillMap = true,
}: HistoryViewProps) {
  const {
    copiedUrl,
    isClearingHistory,
    clearConfirmOpen,
    draftToContinue,
    historyFilter,
    managementOpen,
    selectedRecordIds,
    openRowMenuId,
    headerMenuOpen,
    actionDialog,
    actionTargets,
    actionError,
    isRunningAction,
    deleteFailureIds,
    actionErrorRef,
    isCompact,
    pageSize,
    totalRecords,
    totalPages,
    safeCurrentPage,
    startIndex,
    endIndex,
    paginatedHistory,
    submittedHistory,
    pendingHistory,
    selectedRecords,
    actionAvailableTargets,
    actionPendingCount,
    actionSubmittedCount,
    setClearConfirmOpen,
    setCurrentPage,
    setDraftToContinue,
    setHistoryFilter,
    setManagementOpen,
    setSelectedRecordIds,
    setOpenRowMenuId,
    setHeaderMenuOpen,
    setActionTargets,
    handleToggleCompact,
    handlePageSizeChange,
    openActionDialog,
    closeActionDialog,
    toggleSelected,
    handleSelectCurrentPage,
    handleActionSubmit,
    handleDeleteFailuresOnly,
    handleOpenClearConfirm,
    handleConfirmClear,
    handleCopyUrl,
  } = useHistoryManagement({
    history,
    compactLayout,
    onUpdateCompactLayout,
    pageSize: propPageSize,
    onUpdatePageSize,
    onClearHistory,
    onCleanupEvidence,
    onDeleteHistoryEntries,
  });

  const renderBanStatus = (row: HistoryRecord) => {
    if (isPendingRecord(row)) {
      return <span style={{ color: 'var(--color-text-secondary)' }}>-</span>;
    }
    const s = (row.ban_status || '').trim().toLowerCase();
    const isBanned = s === 'banned' || s === '已制裁' || s === '已封鎖' || Boolean(row.ban_date);
    const resultText = row.ban_result || '已封鎖';
    const maskedName = row.ban_masked_name || '';
    const announcementUrl = (row.ban_announcement_url || '').trim();

    if (isBanned) {
      const tooltipMsg = maskedName
        ? `官方公告命中：${maskedName}（${resultText}）`
        : `官方處分結果：${resultText}`;

      return (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <Tooltip content={tooltipMsg}>
            <Badge
              variant="danger"
              size="sm"
              icon={ShieldAlert}
              tabIndex={0}
              role="status"
              aria-label={`已封鎖：${resultText}`}
            >
              已封鎖
            </Badge>
          </Tooltip>
          {announcementUrl && (
            <IconButton
              icon={ExternalLink}
              size="sm"
              variant="ghost"
              tooltip="開啟官方處分公告"
              aria-label="開啟官方處分公告"
              onClick={() => onOpenUrl(announcementUrl)}
            />
          )}
        </div>
      );
    }

    if (s === 'unbanned' || s === '未被制裁' || s === '未封鎖') {
      return (
        <Badge variant="success" size="sm" icon={ShieldCheck}>
          未封鎖
        </Badge>
      );
    }

    if (s === 'investigating' || s === '審查中') {
      return (
        <Badge variant="warning" size="sm" icon={Clock}>
          查詢中
        </Badge>
      );
    }

    return (
      <Badge variant="default" size="sm">
        {row.ban_status && row.ban_status !== 'pending' ? row.ban_status : '查詢中'}
      </Badge>
    );
  };

  const renderReportStatus = (row: HistoryRecord) => {
    if (getSubmissionState(row) === SUBMISSION_DRAFT) {
      return (
        <Badge variant={row.media_available === false ? 'danger' : 'warning'} size="sm">
          {row.media_available === false ? '檔案遺失' : '尚未送出'}
        </Badge>
      );
    }
    if (getSubmissionState(row) === SUBMISSION_AWAITING_MANUAL) {
      return (
        <Badge variant="warning" size="sm">
          待手動檢舉
        </Badge>
      );
    }
    return renderUploadStatus(row.upload_status || row.status);
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

  const renderEvidenceState = (row: HistoryRecord, evidenceUrl: string) => {
    const isCopied = copiedUrl === evidenceUrl;
    const remoteState = row.remote_evidence_state;
    const isTrashed = remoteState === 'trashed';
    const cleanupError = remoteState === 'error' || Boolean(row.remote_cleanup_error);
    const hasLocalCleaned = Boolean(row.local_evidence_cleaned_at);

    return (
      <div className="history-evidence-cell">
        {evidenceUrl && !isTrashed ? (
          <div className="history-actions">
            <IconButton
              variant="ghost"
              size="sm"
              icon={ExternalLink}
              onClick={() => onOpenUrl(evidenceUrl)}
              tooltip="開啟雲端證據連結"
            />
            <IconButton
              variant="ghost"
              size="sm"
              icon={isCopied ? Check : Copy}
              onClick={() => void handleCopyUrl(evidenceUrl)}
              tooltip={isCopied ? '已複製雲端證據連結' : '複製雲端證據連結'}
            />
          </div>
        ) : isTrashed ? (
          <Badge variant="default" size="sm" icon={Cloud}>
            Drive 已移至垃圾桶
          </Badge>
        ) : getSubmissionState(row) === SUBMISSION_DRAFT ? (
          <span className="history-evidence-muted">尚未上傳</span>
        ) : (
          <span className="history-evidence-muted">無雲端連結</span>
        )}
        {cleanupError && (
          <Badge variant="danger" size="sm">
            Drive 清理失敗
          </Badge>
        )}
        {hasLocalCleaned && (
          <Badge variant="default" size="sm">
            本機已清理
          </Badge>
        )}
        {row.evidence_provider === 'discord' && evidenceUrl && (
          <span className="history-evidence-muted">Discord 證據需手動刪除</span>
        )}
      </div>
    );
  };

  const formatBanDate = (dateStr?: string) => {
    if (!dateStr || dateStr.trim() === '') return '-';
    // Return only YYYY-MM-DD
    const match = dateStr.match(/^\d{4}-\d{2}-\d{2}/);
    if (match) return match[0];
    return dateStr.split(' ')[0] || '-';
  };

  const syncMessage =
    sanctionSyncStatus?.message ||
    (sanctionSyncStatus?.phase === 'fetching' &&
    sanctionSyncStatus?.current &&
    sanctionSyncStatus?.total
      ? `正在檢查第 ${sanctionSyncStatus.current}/${sanctionSyncStatus.total} 篇公告`
      : '正在同步官方公告…');
  const recognitionEnabled = ocrAutofillId || ocrAutofillMap;
  const recognitionScope =
    ocrAutofillId && ocrAutofillMap
      ? '角色 ID 與地圖'
      : ocrAutofillId
        ? '角色 ID'
        : ocrAutofillMap
          ? '地圖'
          : '';

  return (
    <div
      className="card-section"
      style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}
    >
      <div className="history-view-header">
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

        <div className="history-view-header-actions">
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
            disabled={isCheckingSanctions || !onCheckSanctions || submittedHistory.length === 0}
            aria-busy={isCheckingSanctions}
            data-testid="check-sanction-status"
          >
            {isCheckingSanctions ? '檢查中…' : '檢查官方處分狀態'}
          </Button>
          {history.length > 0 && (
            <>
              <Button
                variant={managementOpen ? 'primary' : 'outline'}
                size="md"
                icon={managementOpen ? X : ListChecks}
                onClick={() => {
                  setManagementOpen((open) => !open);
                  setSelectedRecordIds([]);
                  setOpenRowMenuId(null);
                }}
                aria-pressed={managementOpen}
              >
                {managementOpen ? '完成' : '管理紀錄'}
              </Button>
              <div className="history-header-more-wrap">
                <IconButton
                  icon={MoreHorizontal}
                  size="md"
                  variant="ghost"
                  tooltip="更多歷史紀錄操作"
                  data-testid="history-more-actions"
                  aria-expanded={headerMenuOpen}
                  onClick={() => setHeaderMenuOpen((open) => !open)}
                />
                {headerMenuOpen && (
                  <div className="history-header-menu" role="menu" aria-label="更多歷史紀錄操作">
                    <button
                      type="button"
                      role="menuitem"
                      className="history-menu-item"
                      onClick={() => {
                        handleToggleCompact();
                        setHeaderMenuOpen(false);
                      }}
                    >
                      {isCompact ? (
                        <Rows size={16} aria-hidden="true" />
                      ) : (
                        <LayoutList size={16} aria-hidden="true" />
                      )}
                      <span>{isCompact ? '切換為標準排列' : '切換為緊湊排列'}</span>
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      className="history-menu-item history-menu-item-danger"
                      onClick={handleOpenClearConfirm}
                      disabled={
                        (!onClearHistory && !onDeleteHistoryEntries) ||
                        isCheckingSanctions ||
                        isClearingHistory
                      }
                    >
                      <Trash2 size={16} aria-hidden="true" />
                      <span>清空歷史紀錄</span>
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Sanction Sync Diagnostics Banner */}
      <div className={`history-sync-banner ${isCheckingSanctions ? 'is-checking' : ''}`.trim()}>
        <div
          className="history-sync-content"
          style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}
        >
          <span
            style={{
              fontWeight: 600,
              color: 'var(--color-text-heading)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            官方處分公告檢查：
          </span>
          {isCheckingSanctions ? (
            <span style={{ color: 'var(--color-primary)', fontWeight: 600 }}>{syncMessage}</span>
          ) : (
            <span>
              已同步遊戲官方處分公告，共 <strong>{submittedHistory.length}</strong> 筆已送出紀錄（
              <strong style={{ color: 'var(--color-danger)' }}>
                {
                  submittedHistory.filter(
                    (h) => (h.ban_status || '').toLowerCase() === 'banned' || Boolean(h.ban_date)
                  ).length
                }{' '}
                筆已封鎖
              </strong>
              ，
              <strong style={{ color: 'var(--color-status-success)' }}>
                {
                  submittedHistory.filter(
                    (h) => (h.ban_status || '').toLowerCase() === 'unbanned' && !h.ban_date
                  ).length
                }{' '}
                筆未封鎖
              </strong>
              ）
            </span>
          )}
        </div>
        <span className="history-sync-meta">
          上次完整檢查：
          {formatLastSyncTime(lastCompleteSyncAt || sanctionSyncStatus?.last_complete_sync_at)}
        </span>
        <div
          className="history-sync-link"
          style={{ display: 'flex', alignItems: 'center', gap: '12px' }}
        >
          <a
            href="https://maplestoryclassic.beanfun.com/main?section=mBulletin&kind=758"
            target="_blank"
            rel="noreferrer"
            onClick={(e) => {
              e.preventDefault();
              onOpenUrl('https://maplestoryclassic.beanfun.com/main?section=mBulletin&kind=758');
            }}
            className="history-sync-anchor"
          >
            開啟官方處分公告
            <ExternalLink size={12} />
          </a>
        </div>
      </div>

      <div className="history-filter-bar" role="toolbar" aria-label="歷史紀錄篩選">
        {(
          [
            ['all', `全部 ${history.length}`],
            ['pending', `待處理 ${pendingHistory.length}`],
            ['submitted', `已完成 ${submittedHistory.length}`],
          ] as const
        )
          .filter(([value]) => value !== 'pending' || pendingHistory.length > 0)
          .map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={`history-filter-button ${historyFilter === value ? 'active' : ''}`.trim()}
              onClick={() => setHistoryFilter(value)}
              aria-pressed={historyFilter === value}
            >
              {label}
            </button>
          ))}
      </div>

      {managementOpen && (
        <div className="history-selection-toolbar" role="toolbar" aria-label="管理歷史紀錄">
          <span className="history-selection-count">已選 {selectedRecordIds.length} 筆</span>
          <Button variant="ghost" size="sm" onClick={handleSelectCurrentPage}>
            全選本頁
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setSelectedRecordIds([])}>
            清除選取
          </Button>
          <Button
            variant="danger"
            size="sm"
            icon={Trash2}
            disabled={!selectedRecordIds.length}
            onClick={() => openActionDialog('delete', selectedRecords)}
          >
            刪除所選紀錄
          </Button>
        </div>
      )}

      <div className="history-table-container" style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        {totalRecords > 0 ? (
          <table className={`history-table ${isCompact ? 'compact' : ''}`.trim()}>
            <thead>
              <tr>
                {managementOpen && (
                  <th className="history-select-column">
                    <input
                      type="checkbox"
                      aria-label="全選本頁紀錄"
                      checked={
                        paginatedHistory.length > 0 &&
                        paginatedHistory.every((record, index) =>
                          selectedRecordIds.includes(getHistoryRecordId(record, startIndex + index))
                        )
                      }
                      onChange={(event) => {
                        if (event.target.checked) handleSelectCurrentPage();
                        else {
                          const pageIds = paginatedHistory.map((record, index) =>
                            getHistoryRecordId(record, startIndex + index)
                          );
                          setSelectedRecordIds((current) =>
                            current.filter((recordId) => !pageIds.includes(recordId))
                          );
                        }
                      }}
                    />
                  </th>
                )}
                <th>檢舉時間</th>
                <th>嫌疑人 ID</th>
                <th>伺服器</th>
                <th>所在地圖</th>
                <th>檢舉狀態</th>
                <th>官方處分狀態</th>
                <th>處分時間</th>
                <th style={{ textAlign: 'center' }}>證據連結</th>
                <th style={{ textAlign: 'center' }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {paginatedHistory.map((row, idx) => {
                const recordId = getHistoryRecordId(row, startIndex + idx);
                const cleanupTargets = getCleanupTargets(row);
                const key = recordId;
                const evidenceUrl = (row.evidence_url || row.url || '').trim();

                return (
                  <tr key={key}>
                    {managementOpen && (
                      <td className="history-select-column">
                        <input
                          type="checkbox"
                          aria-label={`選取紀錄 ${row.suspect_id || recordId}`}
                          checked={selectedRecordIds.includes(recordId)}
                          onChange={() => toggleSelected(recordId)}
                        />
                      </td>
                    )}
                    <td className="cell-date">{row.timestamp || row.time || '-'}</td>
                    <td className="cell-suspect">{row.suspect_id || row.id || '-'}</td>
                    <td className="cell-nowrap">{row.server || '-'}</td>
                    <td>{row.map_name || row.map || '-'}</td>
                    <td className="cell-nowrap">{renderReportStatus(row)}</td>
                    <td className="cell-nowrap">{renderBanStatus(row)}</td>
                    <td className="cell-date">{formatBanDate(row.ban_date)}</td>
                    <td className="cell-nowrap" style={{ textAlign: 'center' }}>
                      {renderEvidenceState(row, evidenceUrl)}
                    </td>
                    <td className="cell-nowrap history-operation-cell">
                      <div className="history-row-actions">
                        {!managementOpen && getSubmissionState(row) === SUBMISSION_DRAFT ? (
                          <Tooltip
                            content={
                              row.media_available === false
                                ? '找不到本機證據檔案，無法繼續處理'
                                : '選擇如何繼續處理這份檢舉'
                            }
                          >
                            <span style={{ display: 'inline-flex' }}>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setDraftToContinue(row)}
                                disabled={row.media_available === false || !onContinueDraft}
                                data-testid={`continue-draft-${row.record_id || idx}`}
                              >
                                繼續處理
                              </Button>
                            </span>
                          </Tooltip>
                        ) : !managementOpen &&
                          getSubmissionState(row) === SUBMISSION_AWAITING_MANUAL ? (
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => onContinueManual?.(row)}
                            disabled={!onContinueManual}
                            data-testid={`continue-manual-${row.record_id || idx}`}
                          >
                            繼續手動檢舉
                          </Button>
                        ) : null}
                        {!managementOpen && (
                          <div className="history-row-menu-wrap">
                            <IconButton
                              icon={MoreHorizontal}
                              size="sm"
                              variant="ghost"
                              tooltip="更多操作"
                              aria-expanded={openRowMenuId === recordId}
                              onClick={() =>
                                setOpenRowMenuId((current) =>
                                  current === recordId ? null : recordId
                                )
                              }
                            />
                            {openRowMenuId === recordId && (
                              <div className="history-row-menu" role="menu" aria-label="紀錄操作">
                                {isSubmittedRecord(row) && cleanupTargets.length > 0 && (
                                  <button
                                    type="button"
                                    role="menuitem"
                                    className="history-menu-item"
                                    onClick={() => openActionDialog('cleanup', [row])}
                                  >
                                    <Cloud size={16} aria-hidden="true" />
                                    <span>清理證據</span>
                                  </button>
                                )}
                                <button
                                  type="button"
                                  role="menuitem"
                                  className="history-menu-item history-menu-item-danger"
                                  onClick={() => openActionDialog('delete', [row])}
                                >
                                  <Trash2 size={16} aria-hidden="true" />
                                  <span>
                                    {getSubmissionState(row) === SUBMISSION_DRAFT
                                      ? '刪除草稿'
                                      : getSubmissionState(row) === SUBMISSION_AWAITING_MANUAL
                                        ? '放棄這筆檢舉'
                                        : '刪除紀錄'}
                                  </span>
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <div className="history-empty-state" role="status">
            <span className="history-empty-icon" aria-hidden="true">
              <ShieldCheck size={30} strokeWidth={1.6} />
            </span>
            <span>{history.length > 0 ? '目前篩選沒有符合的紀錄' : '目前尚無歷史檢舉紀錄'}</span>
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
            <div className="history-page-size-select">
              <Dropdown<number>
                options={[
                  { value: 10, label: '10 筆 / 頁' },
                  { value: 15, label: '15 筆 / 頁' },
                  { value: 30, label: '30 筆 / 頁' },
                  { value: 50, label: '50 筆 / 頁' },
                  { value: 100, label: '100 筆 / 頁' },
                ]}
                value={pageSize}
                onChange={handlePageSizeChange}
                ariaLabel="每頁顯示筆數"
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

      {actionDialog && (
        <Dialog
          isOpen={true}
          onClose={isRunningAction ? undefined : closeActionDialog}
          title={actionDialog.kind === 'cleanup' ? '清理證據' : '刪除紀錄？'}
          titleIcon={actionDialog.kind === 'cleanup' ? Cloud : Trash2}
          maxWidth="480px"
          footer={
            <div className="history-action-dialog-footer">
              <Button
                variant="outline"
                size="md"
                onClick={closeActionDialog}
                disabled={isRunningAction}
              >
                取消
              </Button>
              {deleteFailureIds.length > 0 && actionDialog.kind === 'delete' ? (
                <>
                  <Button
                    variant="outline"
                    size="md"
                    onClick={handleActionSubmit}
                    loading={isRunningAction}
                    disabled={isRunningAction}
                  >
                    {actionTargets.includes('google_drive') ? '重試 Drive 清理' : '重試清理'}
                  </Button>
                  <Button
                    variant="danger"
                    size="md"
                    onClick={handleDeleteFailuresOnly}
                    loading={isRunningAction}
                    disabled={isRunningAction}
                  >
                    只刪除紀錄
                  </Button>
                </>
              ) : (
                <Button
                  variant={actionDialog.kind === 'delete' ? 'danger' : 'primary'}
                  size="md"
                  onClick={handleActionSubmit}
                  loading={isRunningAction}
                  disabled={
                    isRunningAction ||
                    (actionDialog.kind === 'cleanup' && actionTargets.length === 0)
                  }
                >
                  {actionDialog.kind === 'cleanup' ? '清理所選證據' : '刪除紀錄'}
                </Button>
              )}
            </div>
          }
        >
          {actionDialog.kind === 'delete' ? (
            <div className="history-action-dialog-copy">
              <p>
                刪除後將不再顯示這 {actionDialog.records.length} 筆紀錄，也會停止追蹤官方處分結果。
              </p>
              <div className="history-action-dialog-summary">
                待處理 {actionPendingCount} 筆・已完成 {actionSubmittedCount} 筆
              </div>
            </div>
          ) : (
            <div className="history-action-dialog-copy">
              <p>選擇要清理的證據。清理證據不會刪除回報紀錄。</p>
            </div>
          )}

          {actionAvailableTargets.length > 0 && (
            <div className="history-evidence-targets" role="group" aria-label="證據清理目標">
              {actionAvailableTargets.includes('local') && (
                <label className="history-evidence-target">
                  <input
                    type="checkbox"
                    checked={actionTargets.includes('local')}
                    onChange={() =>
                      setActionTargets((current) =>
                        current.includes('local')
                          ? current.filter((target) => target !== 'local')
                          : [...current, 'local']
                      )
                    }
                    disabled={isRunningAction}
                  />
                  <span>一併刪除本機證據</span>
                </label>
              )}
              {actionAvailableTargets.includes('google_drive') && (
                <label className="history-evidence-target">
                  <input
                    type="checkbox"
                    checked={actionTargets.includes('google_drive')}
                    onChange={() =>
                      setActionTargets((current) =>
                        current.includes('google_drive')
                          ? current.filter((target) => target !== 'google_drive')
                          : [...current, 'google_drive']
                      )
                    }
                    disabled={isRunningAction}
                  />
                  <span>將 Google Drive 檔案移至垃圾桶</span>
                </label>
              )}
            </div>
          )}

          {actionDialog.records.some((record) => record.evidence_provider === 'discord') && (
            <p className="history-evidence-note">
              Discord 證據不會由本工具刪除，請在 Discord 中手動處理。
            </p>
          )}
          {actionError && (
            <div ref={actionErrorRef} className="history-action-error" role="alert" tabIndex={-1}>
              {actionError}
            </div>
          )}
        </Dialog>
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
                variant="danger"
                size="md"
                onClick={handleConfirmClear}
                loading={isClearingHistory}
                disabled={isClearingHistory}
                data-testid="confirm-clear-history-button"
              >
                清空歷史紀錄
              </Button>
            </div>
          }
        >
          <div
            style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem', lineHeight: '1.5' }}
          >
            確定要清空本機的所有檢舉歷史紀錄嗎？
            <div className="history-clear-warning">此操作將永久刪除本機紀錄，無法復原。</div>
          </div>
        </Dialog>
      )}

      {draftToContinue && (
        <Dialog
          isOpen={true}
          onClose={() => setDraftToContinue(null)}
          title="繼續處理檢舉"
          titleIcon={ScanSearch}
          maxWidth="480px"
          footer={
            <div className="resume-draft-footer">
              <Button variant="outline" size="md" onClick={() => setDraftToContinue(null)}>
                取消
              </Button>
              <div className="resume-draft-actions">
                <Button
                  variant="secondary"
                  size="md"
                  icon={FileText}
                  onClick={() => {
                    onContinueDraft?.(draftToContinue, false);
                    setDraftToContinue(null);
                  }}
                  data-testid="continue-draft-with-saved-data"
                >
                  直接開啟表單
                </Button>
                <Button
                  variant="primary"
                  size="md"
                  icon={ScanSearch}
                  disabled={!recognitionEnabled}
                  onClick={() => {
                    onContinueDraft?.(draftToContinue, true);
                    setDraftToContinue(null);
                  }}
                  data-testid="continue-draft-with-recognition"
                >
                  依設定重新辨識
                </Button>
              </div>
            </div>
          }
        >
          <div className="resume-draft-choice">
            <p>要直接使用已儲存的資料，還是先重新辨識這份證據？</p>
            <div
              className={`resume-draft-setting ${recognitionEnabled ? '' : 'disabled'}`.trim()}
              role="status"
            >
              {recognitionEnabled
                ? `依目前設定，將重新辨識：${recognitionScope}。`
                : '目前已關閉角色 ID 與地圖辨識；如需重新辨識，請先到設定開啟。'}
            </div>
          </div>
        </Dialog>
      )}
    </div>
  );
}
