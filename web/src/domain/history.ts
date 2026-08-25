import type { EvidenceCleanupTarget, HistoryRecord } from '../types';

export type HistoryFilter = 'all' | 'pending' | 'submitted';
export type HistorySubmissionState = 'draft' | 'awaiting_manual' | 'submitted';
export const SUBMISSION_DRAFT: HistorySubmissionState = 'draft';
export const SUBMISSION_AWAITING_MANUAL: HistorySubmissionState = 'awaiting_manual';
export const SUBMISSION_SUBMITTED: HistorySubmissionState = 'submitted';

/**
 * History records written by older versions may omit submission_state. Those
 * records represent completed submissions, so the domain default is submitted.
 */
export function getSubmissionState(record: HistoryRecord): HistorySubmissionState {
  return record.submission_state || SUBMISSION_SUBMITTED;
}

export function isPendingRecord(record: HistoryRecord): boolean {
  const state = getSubmissionState(record);
  return state === SUBMISSION_DRAFT || state === SUBMISSION_AWAITING_MANUAL;
}

export function isSubmittedRecord(record: HistoryRecord): boolean {
  return getSubmissionState(record) === SUBMISSION_SUBMITTED;
}

export function filterHistoryRecords(
  history: HistoryRecord[],
  filter: HistoryFilter
): HistoryRecord[] {
  if (filter === 'pending') return history.filter(isPendingRecord);
  if (filter === 'submitted') return history.filter(isSubmittedRecord);
  return history;
}

export function getHistoryRecordId(record: HistoryRecord, index: number): string {
  return record.record_id || `history-${record.timestamp || record.time || 'item'}-${index}`;
}

export function getCleanupTargets(record: HistoryRecord): EvidenceCleanupTarget[] {
  const targets: EvidenceCleanupTarget[] = [];
  if (record.media_cleanup_eligible) targets.push('local');
  if (
    record.evidence_provider === 'gdrive' &&
    record.remote_evidence_state !== 'trashed' &&
    Boolean(record.remote_evidence_id)
  ) {
    targets.push('google_drive');
  }
  return targets;
}
