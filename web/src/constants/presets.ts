import type { HistoryRecord } from '../types';

export type PresetKey = 'ultra_fast' | 'smooth' | 'balanced' | 'high_fps' | 'extreme';

export interface RecordingPresetOption {
  key: PresetKey;
  label: string;
  duration: number;
  fps: number;
  replay: number;
  description: string;
}

export const RECORDING_PRESETS: RecordingPresetOption[] = [
  {
    key: 'ultra_fast',
    label: '極速 / 低負載',
    duration: 5,
    fps: 15,
    replay: 10,
    description: '5秒 / 15 FPS / 循環 10秒',
  },
  {
    key: 'smooth',
    label: '流暢',
    duration: 6,
    fps: 20,
    replay: 15,
    description: '6秒 / 20 FPS / 循環 15秒',
  },
  {
    key: 'balanced',
    label: '平衡 (推薦)',
    duration: 8,
    fps: 20,
    replay: 20,
    description: '8秒 / 20 FPS / 循環 20秒',
  },
  {
    key: 'high_fps',
    label: '高影格',
    duration: 8,
    fps: 30,
    replay: 25,
    description: '8秒 / 30 FPS / 循環 25秒',
  },
  {
    key: 'extreme',
    label: '完整保留',
    duration: 10,
    fps: 30,
    replay: 30,
    description: '10秒 / 30 FPS / 循環 30秒',
  },
];

export function detectPresetKey(
  duration?: number,
  fps?: number,
  replay?: number
): PresetKey | 'custom' {
  const match = RECORDING_PRESETS.find(
    (p) => p.duration === duration && p.fps === fps && p.replay === replay
  );
  return match ? match.key : 'custom';
}

export function getPresetIndex(key?: string): number {
  const idx = RECORDING_PRESETS.findIndex((p) => p.key === key);
  return idx >= 0 ? idx : 2; // Default to balanced (index 2)
}

export const DEFAULT_MOCK_HISTORY: HistoryRecord[] = [
  {
    record_id: 'mock-1',
    timestamp: '2026-08-13 21:45:10',
    suspect_id: '下次我還要玩',
    server: '雪吉拉',
    map_name: '地鐵一號線｜地區01',
    upload_status: 'success',
    evidence_url: 'https://drive.google.com/file/d/1lokRlggA5Ul5h4rCyO_f3UrW7pkk5gU3/view?usp=drivesdk',
    ban_status: 'pending',
  },
  {
    record_id: 'mock-2',
    timestamp: '2026-08-10 10:30:22',
    suspect_id: '你怎麼知道',
    server: '雪吉拉',
    map_name: '隱密之地：幽靈船',
    upload_status: 'success',
    evidence_url: 'https://drive.google.com/file/d/1eI1wJ_bX8Z6_xK2_b5Z_q4A2/view',
    ban_status: 'pending',
  },
  {
    record_id: 'mock-3',
    timestamp: '2026-08-03 19:15:05',
    suspect_id: 'fivefivefive',
    server: '雪吉拉',
    map_name: '天空之城：散步路 II',
    upload_status: 'success',
    evidence_url: 'https://drive.google.com/file/d/1vC3zY_wA1B2_cD4_eF6_gH8/view',
    ban_status: 'pending',
  },
  {
    record_id: 'mock-4',
    timestamp: '2026-08-17 18:02:40',
    suspect_id: '有1.4了',
    server: '雪吉拉',
    map_name: '南部森林訓練場 I',
    upload_status: 'success',
    evidence_url: 'https://drive.google.com/file/d/1pL9kM_nO3P4_qR5_sT7_uV9/view',
    ban_status: 'pending',
  },
];
