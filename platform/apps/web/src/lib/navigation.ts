export type NavItem = Readonly<{
  href: '/dashboard' | '/search' | '/sources' | '/research' | '/projects';
  label: string;
  description: string;
}>;

export const NAV_ITEMS: readonly NavItem[] = [
  { href: '/dashboard', label: 'لوحة العمل', description: 'نظرة تشغيلية على المنصة' },
  { href: '/search', label: 'البحث', description: 'بحث عربي موثّق وقابل للتتبع' },
  { href: '/sources', label: 'المصادر', description: 'إدارة وفحص مصادر المعرفة' },
  { href: '/research', label: 'الأبحاث', description: 'مساحات العمل والتحقيق' },
  { href: '/projects', label: 'المشاريع', description: 'تنظيم العمل والنتائج' },
] as const;
