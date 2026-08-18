import { LucideIcon, LucideProps } from 'lucide-react';
import * as LucideIcons from 'lucide-react';

export interface DynamicIconProps extends LucideProps {
  name: string;
}

export const POPULAR_LUCIDE_ICONS: {
  name: string;
  label: string;
  icon: LucideIcon;
}[] = [
  { name: 'Globe', label: '官方網頁 (Globe)', icon: LucideIcons.Globe },
  { name: 'ShieldAlert', label: '檢舉盾牌 (ShieldAlert)', icon: LucideIcons.ShieldAlert },
  { name: 'Link', label: '超連結 (Link)', icon: LucideIcons.Link },
  { name: 'FileText', label: '文件指南 (FileText)', icon: LucideIcons.FileText },
  { name: 'MessageSquare', label: '討論專區 (MessageSquare)', icon: LucideIcons.MessageSquare },
  { name: 'Youtube', label: '影音頻道 (Youtube)', icon: LucideIcons.Youtube },
  { name: 'Twitch', label: '直播實況 (Twitch)', icon: LucideIcons.Twitch },
  { name: 'Gamepad2', label: '遊戲專區 (Gamepad2)', icon: LucideIcons.Gamepad2 },
  { name: 'Search', label: '資料庫搜尋 (Search)', icon: LucideIcons.Search },
  { name: 'Bookmark', label: '常用書籤 (Bookmark)', icon: LucideIcons.Bookmark },
  { name: 'Flame', label: '熱門情報 (Flame)', icon: LucideIcons.Flame },
  { name: 'Zap', label: '快速傳送 (Zap)', icon: LucideIcons.Zap },
  { name: 'Sparkles', label: '活動公告 (Sparkles)', icon: LucideIcons.Sparkles },
  { name: 'Folder', label: '雲端資料夾 (Folder)', icon: LucideIcons.Folder },
  { name: 'Compass', label: '攻略地圖 (Compass)', icon: LucideIcons.Compass },
  { name: 'HelpCircle', label: '常見問答 (HelpCircle)', icon: LucideIcons.HelpCircle },
  { name: 'ExternalLink', label: '外部站點 (ExternalLink)', icon: LucideIcons.ExternalLink },
  { name: 'Share2', label: '社群分享 (Share2)', icon: LucideIcons.Share2 },
];

export default function DynamicIcon({ name, size = 20, color, ...props }: DynamicIconProps) {
  const IconComponent =
    ((LucideIcons as unknown as Record<string, LucideIcon>)[name] as LucideIcon) || LucideIcons.Globe;
  return <IconComponent size={size} color={color} {...props} />;
}
