import React, { useRef } from 'react';
import { Globe, Plus, ChevronRight } from 'lucide-react';
import { Card, Button, DynamicIcon } from './ui';
import { QuickLinkItem } from '../types';

export interface QuickLinksProps {
  quickLinks?: QuickLinkItem[];
  onOpenLink: (url: string) => void;
  onManageLinks: () => void;
  onAddCustomLink: () => void;
}

export default function QuickLinks({
  quickLinks = [],
  onOpenLink,
  onManageLinks,
  onAddCustomLink,
}: QuickLinksProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Mouse Wheel Horizontal Scroll Listener
  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    if (!scrollRef.current) return;

    const delta = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
    if (delta === 0) return;

    e.preventDefault();
    e.stopPropagation();
    scrollRef.current.scrollLeft += delta;
  };

  const defaultLinks: QuickLinkItem[] = [
    {
      id: 'official-main',
      title: '新楓之谷：經典版',
      url: 'https://maplestoryclassic.beanfun.com/Main',
      icon: 'Globe',
      isDefault: true,
    },
    {
      id: 'official-report',
      title: '外掛檢舉頁面',
      url: 'https://forms.gamania.com/s/eLGg4',
      icon: 'ShieldAlert',
      isDefault: true,
    },
  ];

  const displayLinks = quickLinks && quickLinks.length > 0 ? quickLinks : defaultLinks;

  return (
    <Card
      title="快捷連結"
      titleIcon={Globe}
      headerAction={
        <Button
          variant="outline"
          size="sm"
          icon={ChevronRight}
          iconPosition="right"
          onClick={onManageLinks}
          title="管理快捷連結"
        >
          管理連結
        </Button>
      }
      variant="raised"
    >
      <div className="quick-links-scroll" ref={scrollRef} onWheel={handleWheel}>
        {displayLinks.map((item, index) => (
          <button
            type="button"
            key={item.id || index}
            className="quick-link-card"
            onClick={() => onOpenLink(item.url)}
            title={`${item.title}\n${item.url}`}
          >
            <DynamicIcon
              name={item.icon || 'Globe'}
              size={22}
              color="var(--color-primary)"
            />
            <div className="quick-link-title">{item.title}</div>
          </button>
        ))}

        <button
          type="button"
          className="quick-link-card quick-link-add-card"
          onClick={onAddCustomLink}
          title="新增快捷連結"
        >
          <Plus size={22} className="quick-link-add-icon" />
          <div className="quick-link-title">
            新增連結
          </div>
        </button>
      </div>
    </Card>
  );
}
