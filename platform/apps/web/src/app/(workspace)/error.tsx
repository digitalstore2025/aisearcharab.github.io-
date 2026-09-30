'use client';

export default function WorkspaceError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <section className="page-stack" role="alert">
      <header className="page-header">
        <p className="eyebrow">Error boundary</p>
        <h1>تعذر إكمال الطلب</h1>
        <p>لم يتم تحويل الطلب إلى مزود بديل أو نموذج ذكاء اصطناعي. يمكنك إعادة المحاولة بأمان.</p>
      </header>
      <div>
        <button className="button button-primary" type="button" onClick={reset}>إعادة المحاولة</button>
      </div>
    </section>
  );
}
