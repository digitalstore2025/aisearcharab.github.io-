import Image from 'next/image';
import Link from 'next/link';
import { APP_META } from '@/lib/app-meta';
import { NavLinks } from './nav-links';

export function AppHeader() {
  return (
    <header className="site-header">
      <div className="header-inner shell-width">
        <Link href="/" className="brand" aria-label={`${APP_META.name} — الصفحة الرئيسية`}>
          <Image src="/brand-mark.svg" width={42} height={42} alt="" aria-hidden="true" />
          <span className="brand-copy">
            <strong>{APP_META.name}</strong>
            <small>Arabic Intelligence Workspace</small>
          </span>
        </Link>
        <NavLinks />
      </div>
    </header>
  );
}
