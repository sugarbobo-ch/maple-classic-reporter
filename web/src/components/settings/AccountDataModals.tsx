import { AlertTriangle, ExternalLink, LogOut, Trash2 } from 'lucide-react';
import { Button, Checkbox, Dialog } from '../ui';
import { DisconnectDriveResponse } from '../../types';

interface DisconnectGoogleModalProps {
  isOpen: boolean;
  isDisconnecting: boolean;
  result: DisconnectDriveResponse | null;
  onClose: () => void;
  onConfirm: () => void;
  onOpenPermissions: () => void;
}

export function DisconnectGoogleModal({
  isOpen,
  isDisconnecting,
  result,
  onClose,
  onConfirm,
  onOpenPermissions,
}: DisconnectGoogleModalProps) {
  const manualRevokeRequired = Boolean(result?.requires_manual_revoke);

  return (
    <Dialog
      isOpen={isOpen}
      onClose={isDisconnecting ? undefined : onClose}
      title="登出 Google 帳號？"
      titleIcon={LogOut}
      maxWidth="480px"
      footer={
        manualRevokeRequired ? (
          <>
            <Button variant="outline" size="md" onClick={onClose}>
              關閉
            </Button>
            <Button
              variant="primary"
              size="md"
              icon={ExternalLink}
              onClick={onOpenPermissions}
            >
              前往 Google 帳號權限
            </Button>
          </>
        ) : (
          <>
            <Button variant="outline" size="md" onClick={onClose} disabled={isDisconnecting}>
              取消
            </Button>
            <Button
              variant="danger"
              size="md"
              onClick={onConfirm}
              loading={isDisconnecting}
            >
              登出 Google 帳號
            </Button>
          </>
        )
      }
    >
      {manualRevokeRequired ? (
        <div className="account-action-result" role="status">
          <AlertTriangle size={20} aria-hidden="true" />
          <div>
            <strong>這台電腦已登出</strong>
            <p>{result?.message} 請到 Google 帳號確認並移除此應用程式的權限。</p>
          </div>
        </div>
      ) : (
        <div className="account-action-copy">
          <p>這台電腦會立即移除 Google 登入資料，並嘗試撤銷此應用程式的 Google Drive 權限。</p>
          <p>已經上傳到 Google Drive 的檔案不會被刪除。</p>
        </div>
      )}
    </Dialog>
  );
}

interface ResetUserDataModalProps {
  isOpen: boolean;
  acknowledged: boolean;
  isResetting: boolean;
  errorMessage: string;
  onAcknowledgedChange: (checked: boolean) => void;
  onClose: () => void;
  onConfirm: () => void;
}

export function ResetUserDataModal({
  isOpen,
  acknowledged,
  isResetting,
  errorMessage,
  onAcknowledgedChange,
  onClose,
  onConfirm,
}: ResetUserDataModalProps) {
  return (
    <Dialog
      isOpen={isOpen}
      onClose={isResetting ? undefined : onClose}
      title="刪除所有本機資料？"
      titleIcon={Trash2}
      maxWidth="520px"
      footer={
        <>
          <Button variant="outline" size="md" onClick={onClose} disabled={isResetting}>
            取消
          </Button>
          <Button
            variant="danger"
            size="md"
            onClick={onConfirm}
            loading={isResetting}
            disabled={!acknowledged}
          >
            刪除所有本機資料
          </Button>
        </>
      }
    >
      <div className="reset-data-dialog-copy">
        <p>程式將永久刪除這台電腦上的：</p>
        <ul>
          <li>Google 與 Discord 登入資料、所有設定</li>
          <li>檢舉歷史、處分快取、log 與更新暫存</li>
          <li>所有本機錄影和截圖</li>
        </ul>
        <p>已上傳的 Google Drive 檔案、Discord 訊息及程式本身不會被刪除。</p>
        <Checkbox
          className="reset-data-acknowledgement"
          variant="danger"
          checked={acknowledged}
          onChange={onAcknowledgedChange}
          disabled={isResetting}
          label="我了解錄影、截圖與歷史紀錄將永久刪除"
        />
        {errorMessage && (
          <div className="reset-data-error" role="alert">
            <AlertTriangle size={18} aria-hidden="true" />
            <span>{errorMessage}</span>
          </div>
        )}
      </div>
    </Dialog>
  );
}
