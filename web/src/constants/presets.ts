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
