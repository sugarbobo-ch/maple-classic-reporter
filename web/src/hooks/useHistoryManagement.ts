import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from 'react';
import { useClipboard } from './useClipboard';
import { useToast } from './useToast';
import {
  filterHistoryRecords,
  getCleanupTargets,
  getHistoryRecordId,
  isPendingRecord,
  isSubmittedRecord,
  type HistoryFilter,
} from '../domain/history';
import type {
  EvidenceCleanupResult,
  EvidenceCleanupTarget,
  HistoryDeleteResult,
  HistoryRecord,
} from '../types';

export interface HistoryActionDialog {
  kind: 'cleanup' | 'delete';
  records: HistoryRecord[];
}

export interface HistoryManagementOptions {
  history: HistoryRecord[];
  compactLayout?: boolean;
  onUpdateCompactLayout?: (compact: boolean) => void;
  pageSize?: number;
  onUpdatePageSize?: (size: number) => void;
  onClearHistory?: () => Promise<boolean>;
  onCleanupEvidence?: (
    recordIds: string[],
    targets: EvidenceCleanupTarget[]
  ) => Promise<EvidenceCleanupResult>;
  onDeleteHistoryEntries?: (
    recordIds: string[],
    cleanupTargets?: EvidenceCleanupTarget[]
  ) => Promise<HistoryDeleteResult>;
}

export interface HistoryManagementResult {
  copiedUrl: string;
  isClearingHistory: boolean;
  clearConfirmOpen: boolean;
  draftToContinue: HistoryRecord | null;
  historyFilter: HistoryFilter;
  managementOpen: boolean;
  selectedRecordIds: string[];
  openRowMenuId: string | null;
  headerMenuOpen: boolean;
  actionDialog: HistoryActionDialog | null;
  actionTargets: EvidenceCleanupTarget[];
  actionError: string;
  isRunningAction: boolean;
  deleteFailureIds: string[];
  actionErrorRef: RefObject<HTMLDivElement>;
  isCompact: boolean;
  currentPage: number;
  pageSize: number;
  filteredHistory: HistoryRecord[];
  totalRecords: number;
  totalPages: number;
  safeCurrentPage: number;
  startIndex: number;
  endIndex: number;
  paginatedHistory: HistoryRecord[];
  submittedHistory: HistoryRecord[];
  pendingHistory: HistoryRecord[];
  selectedRecords: HistoryRecord[];
  actionAvailableTargets: EvidenceCleanupTarget[];
  actionPendingCount: number;
  actionSubmittedCount: number;
  setClearConfirmOpen: Dispatch<SetStateAction<boolean>>;
  setCurrentPage: Dispatch<SetStateAction<number>>;
  setDraftToContinue: Dispatch<SetStateAction<HistoryRecord | null>>;
  setHistoryFilter: Dispatch<SetStateAction<HistoryFilter>>;
  setManagementOpen: Dispatch<SetStateAction<boolean>>;
  setSelectedRecordIds: Dispatch<SetStateAction<string[]>>;
  setOpenRowMenuId: Dispatch<SetStateAction<string | null>>;
  setHeaderMenuOpen: Dispatch<SetStateAction<boolean>>;
  setActionTargets: Dispatch<SetStateAction<EvidenceCleanupTarget[]>>;
  handleToggleCompact: () => void;
  handlePageSizeChange: (newSize: number) => void;
  openActionDialog: (kind: HistoryActionDialog['kind'], records: HistoryRecord[]) => void;
  closeActionDialog: () => void;
  toggleSelected: (recordId: string) => void;
  handleSelectCurrentPage: () => void;
  handleActionSubmit: () => Promise<void>;
  handleDeleteFailuresOnly: () => Promise<void>;
  handleOpenClearConfirm: () => void;
  handleConfirmClear: () => Promise<void>;
  handleCopyUrl: (url: string) => Promise<void>;
}

export function useHistoryManagement({
  history,
  compactLayout,
  onUpdateCompactLayout,
  pageSize: propPageSize,
  onUpdatePageSize,
  onClearHistory,
  onCleanupEvidence,
  onDeleteHistoryEntries,
}: HistoryManagementOptions): HistoryManagementResult {
  const { copy } = useClipboard();
  const { toast } = useToast();
  const [copiedUrl, setCopiedUrl] = useState('');
  const [isClearingHistory, setIsClearingHistory] = useState(false);
  const [clearConfirmOpen, setClearConfirmOpen] = useState(false);
  const [draftToContinue, setDraftToContinue] = useState<HistoryRecord | null>(null);
  const [historyFilter, setHistoryFilter] = useState<HistoryFilter>('all');
  const [managementOpen, setManagementOpen] = useState(false);
  const [selectedRecordIds, setSelectedRecordIds] = useState<string[]>([]);
  const [openRowMenuId, setOpenRowMenuId] = useState<string | null>(null);
  const [headerMenuOpen, setHeaderMenuOpen] = useState(false);
  const [actionDialog, setActionDialog] = useState<HistoryActionDialog | null>(null);
  const [actionTargets, setActionTargets] = useState<EvidenceCleanupTarget[]>([]);
  const [actionError, setActionError] = useState('');
  const [isRunningAction, setIsRunningAction] = useState(false);
  const [deleteFailureIds, setDeleteFailureIds] = useState<string[]>([]);
  const actionErrorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (actionError) actionErrorRef.current?.focus();
  }, [actionError]);

  const [isCompact, setIsCompact] = useState<boolean>(() => {
    if (typeof compactLayout === 'boolean') return compactLayout;
    try {
      const saved = localStorage.getItem('maple_history_compact');
      if (saved !== null) return saved === 'true';
    } catch {
      // Local storage can be unavailable; retain the provided layout default.
    }
    return false;
  });

  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(() => {
    if (typeof propPageSize === 'number' && propPageSize > 0) return propPageSize;
    try {
      const saved = localStorage.getItem('maple_history_page_size');
      if (saved) {
        const num = Number(saved);
        if ([10, 15, 30, 50, 100].includes(num)) return num;
      }
    } catch {
      // Local storage can be unavailable; retain the provided page size.
    }
    return 15;
  });

  const handleToggleCompact = () => {
    const next = !isCompact;
    setIsCompact(next);
    try {
      localStorage.setItem('maple_history_compact', String(next));
    } catch {
      // Persisting this preference is optional.
    }
    onUpdateCompactLayout?.(next);
  };

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize);
    setCurrentPage(1);
    try {
      localStorage.setItem('maple_history_page_size', String(newSize));
    } catch {
      // Persisting this preference is optional.
    }
    onUpdatePageSize?.(newSize);
  };

  const filteredHistory = useMemo(
    () => filterHistoryRecords(history, historyFilter),
    [history, historyFilter]
  );
  const totalRecords = filteredHistory.length;
  const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));
  const safeCurrentPage = Math.min(Math.max(1, currentPage), totalPages);
  const startIndex = (safeCurrentPage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, totalRecords);
  const paginatedHistory = filteredHistory.slice(startIndex, endIndex);
  const submittedHistory = history.filter(isSubmittedRecord);
  const pendingHistory = history.filter(isPendingRecord);

  useEffect(() => {
    setCurrentPage(1);
    setSelectedRecordIds([]);
    setOpenRowMenuId(null);
  }, [historyFilter]);

  useEffect(() => {
    if (historyFilter === 'pending' && pendingHistory.length === 0) {
      setHistoryFilter('all');
    }
  }, [historyFilter, pendingHistory.length]);

  useEffect(() => {
    setSelectedRecordIds((current) =>
      current.filter((recordId) => filteredHistory.some((record) => record.record_id === recordId))
    );
  }, [filteredHistory]);

  useEffect(() => {
    if (!openRowMenuId && !headerMenuOpen) return;
    const handleOutsidePointer = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (target.closest('.history-row-menu-wrap, .history-header-more-wrap')) return;
      setOpenRowMenuId(null);
      setHeaderMenuOpen(false);
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpenRowMenuId(null);
        setHeaderMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsidePointer);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleOutsidePointer);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [headerMenuOpen, openRowMenuId]);

  const openActionDialog = (kind: HistoryActionDialog['kind'], records: HistoryRecord[]) => {
    setActionDialog({ kind, records });
    setActionTargets([]);
    setActionError('');
    setDeleteFailureIds([]);
    setOpenRowMenuId(null);
    setHeaderMenuOpen(false);
  };

  const closeActionDialog = () => {
    setActionDialog(null);
    setActionTargets([]);
    setActionError('');
    setDeleteFailureIds([]);
  };

  const toggleSelected = (recordId: string) => {
    setSelectedRecordIds((current) =>
      current.includes(recordId) ? current.filter((id) => id !== recordId) : [...current, recordId]
    );
  };

  const selectedRecords = filteredHistory.filter((record, index) =>
    selectedRecordIds.includes(getHistoryRecordId(record, index))
  );

  const actionAvailableTargets = actionDialog
    ? Array.from(new Set(actionDialog.records.flatMap((record) => getCleanupTargets(record))))
    : [];
  const actionPendingCount = actionDialog ? actionDialog.records.filter(isPendingRecord).length : 0;
  const actionSubmittedCount = actionDialog
    ? actionDialog.records.filter(isSubmittedRecord).length
    : 0;

  const handleSelectCurrentPage = () => {
    const pageIds = paginatedHistory.map((record, index) =>
      getHistoryRecordId(record, startIndex + index)
    );
    setSelectedRecordIds((current) => Array.from(new Set([...current, ...pageIds])));
  };

  const handleActionSubmit = async () => {
    if (!actionDialog || isRunningAction) return;
    const recordIds = (
      deleteFailureIds.length && actionDialog.kind === 'delete'
        ? deleteFailureIds
        : actionDialog.records.map((record, index) => getHistoryRecordId(record, index))
    ).filter((recordId) => !recordId.startsWith('history-'));
    if (!recordIds.length) {
      setActionError('找不到可操作的紀錄 ID。');
      return;
    }
    if (actionDialog.kind === 'cleanup' && !actionTargets.length) {
      setActionError('請至少選擇一個清理目標。');
      return;
    }
    if (!onCleanupEvidence && actionDialog.kind === 'cleanup') {
      setActionError('目前無法清理證據，請使用桌面版程式操作。');
      return;
    }
    if (!onDeleteHistoryEntries && actionDialog.kind === 'delete') {
      setActionError('目前無法刪除紀錄，請使用桌面版程式操作。');
      return;
    }

    setIsRunningAction(true);
    setActionError('');
    try {
      if (actionDialog.kind === 'cleanup') {
        const result = await onCleanupEvidence?.(recordIds, actionTargets);
        if (!result?.success) {
          setActionError(
            result?.message ||
              result?.results?.find((item) => !item.success)?.message ||
              '清理證據失敗，請確認權限後重試。'
          );
          return;
        }
        toast.success('證據清理完成');
        closeActionDialog();
        return;
      }

      const result = await onDeleteHistoryEntries?.(recordIds, actionTargets);
      if (!result?.success) {
        const failedIds = result?.failed_record_ids || [];
        setDeleteFailureIds(failedIds);
        setActionError(
          result?.failed?.[0]?.message ||
            result?.message ||
            '部分紀錄無法刪除，請重試或只刪除紀錄。'
        );
        return;
      }
      toast.success(`已刪除 ${result.deleted_record_ids?.length || recordIds.length} 筆紀錄`);
      setSelectedRecordIds([]);
      closeActionDialog();
    } finally {
      setIsRunningAction(false);
    }
  };

  const handleDeleteFailuresOnly = async () => {
    if (!deleteFailureIds.length || !onDeleteHistoryEntries || isRunningAction) return;
    setIsRunningAction(true);
    setActionError('');
    try {
      const result = await onDeleteHistoryEntries(deleteFailureIds, []);
      if (!result.success) {
        setActionError(result.failed?.[0]?.message || result.message || '仍有紀錄無法刪除。');
        return;
      }
      toast.success(
        `已刪除 ${result.deleted_record_ids?.length || deleteFailureIds.length} 筆紀錄`
      );
      setSelectedRecordIds((current) => current.filter((id) => !deleteFailureIds.includes(id)));
      closeActionDialog();
    } finally {
      setIsRunningAction(false);
    }
  };

  const handleOpenClearConfirm = () => {
    if (onDeleteHistoryEntries) {
      openActionDialog('delete', history);
    } else {
      setClearConfirmOpen(true);
    }
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

  return {
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
    currentPage,
    pageSize,
    filteredHistory,
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
  };
}
