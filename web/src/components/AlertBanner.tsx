import { AlertTriangle, ArrowRight } from 'lucide-react';
import { Button } from './ui';

export interface AlertBannerProps {
  message?: string;
  actionLabel?: string;
  actionLoading?: boolean;
  onStartSettings: () => void;
}

export default function AlertBanner({
  message = '尚未設定檢舉證據上傳目的地',
  actionLabel = '開始設定',
  actionLoading = false,
  onStartSettings,
}: AlertBannerProps) {
  return (
    <div className="alert-banner" role="alert" aria-live="polite">
      <div className="alert-info">
        <AlertTriangle size={18} aria-hidden="true" />
        <span>{message}</span>
      </div>
      <Button
        variant="danger"
        size="sm"
        onClick={onStartSettings}
        loading={actionLoading}
        icon={ArrowRight}
        iconPosition="right"
      >
        {actionLabel}
      </Button>
    </div>
  );
}
