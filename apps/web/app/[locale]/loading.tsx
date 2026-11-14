export default function LocaleLoading() {
  return (
    <main id="main" className="min-h-screen px-6 py-8 md:px-16 md:py-12" aria-busy="true">
      <p className="sr-only">Loading</p>
      <div className="h-8 w-40 bg-muted" />
      <div className="mt-6 h-4 w-64 bg-muted" />
      <div className="mt-10 h-12 max-w-md bg-muted" />
      <div className="mt-3 h-12 max-w-md bg-muted" />
    </main>
  );
}
