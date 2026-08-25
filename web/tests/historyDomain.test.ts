import { describe, expect, it } from 'vitest';
import {
  filterHistoryRecords,
  getCleanupTargets,
  getHistoryRecordId,
  getSubmissionState,
  isPendingRecord,
  isSubmittedRecord,
} from '../src/domain/history';
import type { HistoryRecord } from '../src/types';

describe('history domain module', () => {
  it('treats legacy records without a submission state as submitted', () => {
    const legacyRecord: HistoryRecord = { record_id: 'legacy-1' };

    expect(getSubmissionState(legacyRecord)).toBe('submitted');
    expect(isSubmittedRecord(legacyRecord)).toBe(true);
    expect(isPendingRecord(legacyRecord)).toBe(false);
    expect(filterHistoryRecords([legacyRecord], 'submitted')).toEqual([legacyRecord]);
  });

  it('keeps draft and manual records in the pending view', () => {
    const records: HistoryRecord[] = [
      { record_id: 'draft-1', submission_state: 'draft' },
      { record_id: 'manual-1', submission_state: 'awaiting_manual' },
      { record_id: 'submitted-1', submission_state: 'submitted' },
    ];

    expect(filterHistoryRecords(records, 'pending').map((record) => record.record_id)).toEqual([
      'draft-1',
      'manual-1',
    ]);
    expect(filterHistoryRecords(records, 'submitted').map((record) => record.record_id)).toEqual([
      'submitted-1',
    ]);
  });

  it('derives only managed evidence cleanup targets', () => {
    expect(
      getCleanupTargets({
        record_id: 'drive-1',
        evidence_provider: 'gdrive',
        remote_evidence_id: 'file-1',
        remote_evidence_state: 'available',
        media_cleanup_eligible: true,
      })
    ).toEqual(['local', 'google_drive']);
    expect(
      getCleanupTargets({
        record_id: 'trashed-1',
        evidence_provider: 'gdrive',
        remote_evidence_id: 'file-2',
        remote_evidence_state: 'trashed',
        media_cleanup_eligible: false,
      })
    ).toEqual([]);
  });

  it('preserves stable fallback IDs for records without record_id', () => {
    expect(getHistoryRecordId({ timestamp: '2026-08-25T10:00:00' }, 2)).toBe(
      'history-2026-08-25T10:00:00-2'
    );
  });
});
