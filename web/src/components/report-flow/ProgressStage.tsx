import { Badge } from '../ui';

export interface ProgressStageProps {
  progressPercent: number;
  progressStatus: string;
}

export default function ProgressStage({ progressPercent, progressStatus }: ProgressStageProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--color-text-heading)' }}>
        正在分析檢舉證據...
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.875rem' }}>
        {/* 1. Read recording */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span
            style={{
              color:
                progressPercent >= 20 ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
            }}
          >
            讀取錄影片段
          </span>
          {progressPercent >= 20 ? (
            <Badge variant="success" size="sm">
              完成
            </Badge>
          ) : (
            <Badge variant="primary" size="sm" dot>
              處理中...
            </Badge>
          )}
        </div>

        {/* 2. Keyframes extraction */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span
            style={{
              color:
                progressPercent >= 40 ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
            }}
          >
            截取重點畫面
          </span>
          {progressPercent >= 40 ? (
            <Badge variant="success" size="sm">
              完成
            </Badge>
          ) : progressPercent >= 20 ? (
            <Badge variant="primary" size="sm" dot>
              處理中...
            </Badge>
          ) : (
            <Badge variant="default" size="sm">
              等待中
            </Badge>
          )}
        </div>

        {/* 3. Map recognition */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span
            style={{
              color:
                progressPercent >= 60 ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
              fontWeight: progressPercent >= 40 && progressPercent < 60 ? 700 : 400,
            }}
          >
            辨識地圖名稱
          </span>
          {progressPercent >= 60 ? (
            <Badge variant="success" size="sm">
              完成
            </Badge>
          ) : progressPercent >= 40 ? (
            <Badge variant="primary" size="sm" dot>
              {progressStatus.includes('地圖') && progressStatus.match(/\(([^)]+)\)/)
                ? `處理中 ${progressStatus.match(/\(([^)]+)\)/)?.[0] || ''}`
                : '處理中...'}
            </Badge>
          ) : (
            <Badge variant="default" size="sm">
              等待中
            </Badge>
          )}
        </div>

        {/* 4. Character ID recognition */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span
            style={{
              color:
                progressPercent >= 85 ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
              fontWeight: progressPercent >= 60 && progressPercent < 85 ? 700 : 400,
            }}
          >
            辨識角色 ID
          </span>
          {progressPercent >= 85 ? (
            <Badge variant="success" size="sm">
              完成
            </Badge>
          ) : progressPercent >= 60 ? (
            <Badge variant="primary" size="sm" dot>
              {progressStatus.includes('ID') && progressStatus.match(/\(([^)]+)\)/)
                ? `處理中 ${progressStatus.match(/\(([^)]+)\)/)?.[0] || ''}`
                : '處理中...'}
            </Badge>
          ) : (
            <Badge variant="default" size="sm">
              等待中
            </Badge>
          )}
        </div>

        {/* 5. Organize candidates */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            color:
              progressPercent >= 90 ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
          }}
        >
          <span>整理歷史與候選資料</span>
          {progressPercent >= 100 ? (
            <Badge variant="success" size="sm">
              完成
            </Badge>
          ) : progressPercent >= 85 ? (
            <Badge variant="primary" size="sm" dot>
              處理中...
            </Badge>
          ) : (
            <Badge variant="default" size="sm">
              等待中
            </Badge>
          )}
        </div>
      </div>

      <div style={{ marginTop: '12px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: '0.8rem',
            color: 'var(--color-text-secondary)',
            marginBottom: '6px',
          }}
        >
          <span>
            {progressStatus ||
              (progressPercent >= 100
                ? '分析完成，載入回報表單中...'
                : `正在分析關鍵畫面... (${progressPercent}%)`)}
          </span>
        </div>
        <div
          style={{
            height: '8px',
            backgroundColor: 'var(--color-surface)',
            borderRadius: '4px',
            overflow: 'hidden',
            border: '1px solid var(--color-border)',
          }}
        >
          <div
            className="analysis-progress-fill"
            style={{
              height: '100%',
              width: '100%',
              backgroundColor: 'var(--color-primary)',
              transform: `scaleX(${Math.max(0, Math.min(100, progressPercent)) / 100})`,
              transformOrigin: 'left center',
              transition: 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          />
        </div>
      </div>
    </div>
  );
}
