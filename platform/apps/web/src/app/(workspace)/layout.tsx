import type { ReactNode } from 'react';
import { AppHeader } from '@/components/navigation/app-header';

export default function WorkspaceLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="workspace-frame">
      <AppHeader />
      <main id="main-content" className="workspace-main shell-width">
        {children}
      </main>
      <footer className="workspace-footer">
        <div className="shell-width">AI Search Arab · Production foundation in progress</div>
      </footer>
    </div>
  );
}
