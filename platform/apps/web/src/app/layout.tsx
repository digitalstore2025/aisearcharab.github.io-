import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { APP_META } from '@/lib/app-meta';
import './globals.css';

export const metadata: Metadata = {
  title: { default: APP_META.name, template: `%s | ${APP_META.name}` },
  description: APP_META.description,
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ar" dir="rtl">
      <body>{children}</body>
    </html>
  );
}
