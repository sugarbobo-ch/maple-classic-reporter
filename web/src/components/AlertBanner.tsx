import { AlertTriangle, ArrowRight } from 'lucide-react';
import { Button } from './ui';

export interface AlertBannerProps {
  message?: string;
  onStartSettings: () => void;
}

export default function AlertBanner({
  message = '尚未設定檢舉證據上傳目的地',
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
        icon={ArrowRight}
        iconPosition="right"
      >
        開始設定
      </Button>
    </div>
  );
}
