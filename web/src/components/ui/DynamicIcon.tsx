import { Globe, type LucideProps } from 'lucide-react';
import { ICON_BY_NAME } from './iconCatalog';

export interface DynamicIconProps extends LucideProps {
  name: string;
}

export default function DynamicIcon({ name, size = 20, color, ...props }: DynamicIconProps) {
  const IconComponent = ICON_BY_NAME[name] || Globe;
  return <IconComponent size={size} color={color} {...props} />;
}
