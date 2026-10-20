import { Bot, Box, FileText, Layers, ShoppingBag, Wallet, Shapes } from 'lucide-react';

const icons = {
  general_analysis: FileText,
  ecommerce: ShoppingBag,
  internet_product: Layers,
  hardware_iot: Box,
  ai_llm: Bot,
  finance: Wallet,
};
export function SkillIcon({ id }: { id: string }) {
  const Icon = icons[id as keyof typeof icons] ?? Shapes;
  return (
    <span
      className={`tile-icon ${id === 'ecommerce' ? 'red' : id === 'internet_product' ? 'purple' : id === 'finance' ? 'green' : id === 'hardware_iot' ? 'orange' : 'blue'}`}
    >
      <Icon size={23} />
    </span>
  );
}
