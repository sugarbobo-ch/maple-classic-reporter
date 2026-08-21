import { useState, useEffect } from 'react';
import { Link as LinkIcon } from 'lucide-react';
import { Dialog, Input, Dropdown, Button, DynamicIcon, POPULAR_LUCIDE_ICONS } from './ui';
import { QuickLinkItem, DropdownOption } from '../types';
import { normalizeSafeHttpsUrl } from '../utils';

export interface QuickLinkModalProps {
  linkToEdit?: QuickLinkItem | null;
  onSave: (linkData: QuickLinkItem) => void;
  onClose: () => void;
}

export default function QuickLinkModal({ linkToEdit, onSave, onClose }: QuickLinkModalProps) {
  const [title, setTitle] = useState(linkToEdit ? linkToEdit.title : '');
  const [url, setUrl] = useState(linkToEdit ? linkToEdit.url : '');
  const [icon, setIcon] = useState(linkToEdit ? linkToEdit.icon : 'Globe');
  const [urlError, setUrlError] = useState<string | null>(null);

  useEffect(() => {
    setTitle(linkToEdit ? linkToEdit.title : '');
    setUrl(linkToEdit ? linkToEdit.url : '');
    setIcon(linkToEdit ? linkToEdit.icon : 'Globe');
    setUrlError(null);
  }, [linkToEdit]);

  const iconOptions: DropdownOption<string>[] = POPULAR_LUCIDE_ICONS.map((item) => ({
    value: item.name,
    label: item.label,
    icon: item.icon,
  }));

  const handleSubmit = (e?: React.FormEvent) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!title.trim() || !url.trim()) return;

    const formattedUrl = normalizeSafeHttpsUrl(url);
    if (!formattedUrl) {
      setUrlError('請輸入安全的 HTTPS 網址（不可含帳號、密碼、片段或非 443 埠）。');
      return;
    }
    setUrlError(null);

    onSave({
      id: linkToEdit ? linkToEdit.id : Date.now().toString(),
      title: title.trim(),
      url: formattedUrl,
      icon,
      isDefault: linkToEdit ? linkToEdit.isDefault : false,
    });
  };

  return (
    <Dialog
      isOpen={true}
      onClose={onClose}
      title={linkToEdit ? '編輯快捷連結' : '新增快捷連結'}
      titleIcon={LinkIcon}
      maxWidth="440px"
      footer={
        <>
          <Button variant="outline" size="md" onClick={onClose}>
            取消
          </Button>
          <Button variant="primary" size="md" onClick={handleSubmit}>
            儲存
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="dialog-form-stack">
        <Input
          label="連結名稱"
          placeholder="例如：巴哈姆特討論區"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
        />

        <Input
          label="網址"
          placeholder="https://..."
          value={url}
          error={urlError}
          onChange={(e) => {
            setUrl(e.target.value);
            setUrlError(null);
          }}
          required
        />

        <Dropdown
          label="圖示"
          options={iconOptions}
          value={icon}
          onChange={(val) => setIcon(val)}
        />

        <div className="quick-link-preview-block">
          <label className="ui-input-label">即時預覽效果</label>
          <div className="quick-link-preview" aria-live="polite">
            <DynamicIcon name={icon} size={20} color="var(--color-primary)" />
            <span>{title || '連結標題'}</span>
          </div>
        </div>
      </form>
    </Dialog>
  );
}
