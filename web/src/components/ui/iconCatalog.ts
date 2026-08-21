import {
  Bookmark,
  Compass,
  ExternalLink,
  FileText,
  Flame,
  Folder,
  Gamepad2,
  Globe,
  HelpCircle,
  Link,
  MessageSquare,
  Search,
  Share2,
  ShieldAlert,
  Sparkles,
  Twitch,
  Youtube,
  Zap,
  type LucideIcon,
} from 'lucide-react';

export const POPULAR_LUCIDE_ICONS: {
  name: string;
  label: string;
  icon: LucideIcon;
}[] = [
  { name: 'Globe', label: '官方網頁 (Globe)', icon: Globe },
  { name: 'ShieldAlert', label: '檢舉盾牌 (ShieldAlert)', icon: ShieldAlert },
  { name: 'Link', label: '超連結 (Link)', icon: Link },
  { name: 'FileText', label: '文件指南 (FileText)', icon: FileText },
  { name: 'MessageSquare', label: '討論專區 (MessageSquare)', icon: MessageSquare },
  { name: 'Youtube', label: '影音頻道 (Youtube)', icon: Youtube },
  { name: 'Twitch', label: '直播實況 (Twitch)', icon: Twitch },
  { name: 'Gamepad2', label: '遊戲專區 (Gamepad2)', icon: Gamepad2 },
  { name: 'Search', label: '資料庫搜尋 (Search)', icon: Search },
  { name: 'Bookmark', label: '常用書籤 (Bookmark)', icon: Bookmark },
  { name: 'Flame', label: '熱門情報 (Flame)', icon: Flame },
  { name: 'Zap', label: '快速傳送 (Zap)', icon: Zap },
  { name: 'Sparkles', label: '活動公告 (Sparkles)', icon: Sparkles },
  { name: 'Folder', label: '雲端資料夾 (Folder)', icon: Folder },
  { name: 'Compass', label: '攻略地圖 (Compass)', icon: Compass },
  { name: 'HelpCircle', label: '常見問答 (HelpCircle)', icon: HelpCircle },
  { name: 'ExternalLink', label: '外部站點 (ExternalLink)', icon: ExternalLink },
  { name: 'Share2', label: '社群分享 (Share2)', icon: Share2 },
];

export const ICON_BY_NAME = Object.fromEntries(
  POPULAR_LUCIDE_ICONS.map(({ name, icon }) => [name, icon])
) as Record<string, LucideIcon>;
