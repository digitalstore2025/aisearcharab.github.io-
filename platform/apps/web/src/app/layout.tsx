import type { Metadata } from 'next';
import { IBM_Plex_Sans_Arabic, Noto_Sans_Arabic } from 'next/font/google';
import type { ReactNode } from 'react';
import { APP_META } from '@/lib/app-meta';
import './globals.css';

const bodyFont = IBM_Plex_Sans_Arabic({
  weight: ['400', '500', '600', '700'],
  subsets: ['arabic', 'latin'],
  variable: '--font-body',
  display: 'swap',
});

const headingFont = Noto_Sans_Arabic({
  subsets: ['arabic', 'latin'],
  variable: '--font-heading',
  display: 'swap',
});

export const metadata: Metadata = {
  title: { default: APP_META.name, template: `%s | ${APP_META.name}` },
  description: APP_META.description,
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ar" dir="rtl" className={`${bodyFont.variable} ${headingFont.variable}`}>
      <body>
        <a className="skip-link" href="#main-content">تجاوز إلى المحتوى</a>
        {children}
      </body>
    </html>
  );
}
