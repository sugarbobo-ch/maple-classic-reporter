import React from 'react';
import { Plus, GripVertical, ArrowUp, ArrowDown, Edit2, Trash2 } from 'lucide-react';
import { Button, IconButton, Badge, DynamicIcon } from '../ui';
import { QuickLinkItem } from '../../types';

export interface QuickLinksTabProps {
  quickLinks: QuickLinkItem[];
  draggedIndex: number | null;
  dragOverIndex: number | null;
  onOpenAddModal: () => void;
  onOpenEditModal: (item: QuickLinkItem) => void;
  onDeleteQuickLink: (id: string) => void;
  onMoveQuickLink: (idx: number, direction: 'up' | 'down') => void;
  onDragStart: (e: React.DragEvent, idx: number) => void;
  onDragOver: (e: React.DragEvent, idx: number) => void;
  onDrop: (e: React.DragEvent, idx: number) => void;
  onDragEnd: () => void;
}

export default function QuickLinksTab({
  quickLinks,
  draggedIndex,
  dragOverIndex,
  onOpenAddModal,
  onOpenEditModal,
  onDeleteQuickLink,
  onMoveQuickLink,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
}: QuickLinksTabProps) {
  return (
    <>
      <div className="setting-row no-border">
        <div className="setting-info">
          <span className="setting-label">快捷連結管理</span>
          <span className="setting-desc">管理首頁橫向快捷按鈕，可自由編輯、排序與自訂圖示</span>
        </div>
        <Button
          variant="primary"
          size="md"
          icon={Plus}
          onClick={onOpenAddModal}
        >
          新增連結
        </Button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {quickLinks.map((item, idx) => (
          <div
            key={item.id || idx}
            className={`quick-link-drag-item ${draggedIndex === idx ? 'dragging' : ''} ${
              dragOverIndex === idx ? 'drag-over' : ''
            }`}
            draggable
            onDragStart={(e) => onDragStart(e, idx)}
            onDragOver={(e) => onDragOver(e, idx)}
            onDrop={(e) => onDrop(e, idx)}
            onDragEnd={onDragEnd}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span title="按住拖曳以重新排序" style={{ display: 'flex', alignItems: 'center', cursor: 'grab', flexShrink: 0 }}>
                <GripVertical size={18} color="var(--color-border-strong)" />
              </span>
              <DynamicIcon
                name={item.icon || 'Globe'}
                size={18}
                color="var(--color-primary)"
              />
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>{item.title}</span>
                  {item.isDefault && (
                    <Badge variant="default" style={{ fontSize: '0.7rem', padding: '1px 6px' }}>
                      預設
                    </Badge>
                  )}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
                  {item.url}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
              <IconButton
                icon={ArrowUp}
                size="sm"
                variant="ghost"
                tooltip="向上移動"
                disabled={idx === 0}
                onClick={() => onMoveQuickLink(idx, 'up')}
              />
              <IconButton
                icon={ArrowDown}
                size="sm"
                variant="ghost"
                tooltip="向下移動"
                disabled={idx === quickLinks.length - 1}
                onClick={() => onMoveQuickLink(idx, 'down')}
              />
              <IconButton
                icon={Edit2}
                size="sm"
                variant="ghost"
                tooltip="編輯"
                onClick={() => onOpenEditModal(item)}
              />
              <IconButton
                icon={Trash2}
                size="sm"
                variant="danger"
                tooltip="刪除"
                onClick={() => onDeleteQuickLink(item.id)}
              />
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
