import { useState, useEffect } from 'react';
import { FileText, AlertCircle } from 'lucide-react';
import { Dialog, Input, Textarea, Button } from './ui';
import { ViolationTemplateItem } from '../types';

export interface ViolationTemplateModalProps {
  templateToEdit?: ViolationTemplateItem | null;
  isOpen: boolean;
  onSave: (name: string, content: string) => void;
  onClose: () => void;
}

export default function ViolationTemplateModal({
  templateToEdit,
  isOpen,
  onSave,
  onClose,
}: ViolationTemplateModalProps) {
  const [name, setName] = useState('');
  const [content, setContent] = useState('');

  useEffect(() => {
    if (templateToEdit) {
      setName(templateToEdit.name);
      setContent(templateToEdit.content);
    } else {
      setName('');
      setContent('');
    }
  }, [templateToEdit, isOpen]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!name.trim() || !content.trim()) return;
    onSave(name.trim(), content.trim());
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title={templateToEdit ? '編輯違規範本' : '新增違規範本'}
      titleIcon={FileText}
      maxWidth="460px"
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
      <form
        onSubmit={handleSubmit}
        style={{ display: 'flex', flexDirection: 'column', gap: '14px', padding: '4px 0' }}
      >
        <Input
          label="範本名稱"
          placeholder="例如：自動打怪／定點外掛"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />

        <Textarea
          label="違規說明內容"
          placeholder="例如：使用未授權外掛程式自動施放技能與打怪，多次密語與喊話皆無任何回應。"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={3}
          helperText={
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <AlertCircle size={14} style={{ flexShrink: 0 }} color="var(--color-warning)" />
              <span>提醒：由於官方檢舉表單限制，送出時換行將自動縮減合併為一行。</span>
            </span>
          }
          required
        />
      </form>
    </Dialog>
  );
}
