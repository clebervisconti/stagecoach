export default function AppLoading() {
  return (
    <div className="px-6 py-8" aria-busy="true">
      <p className="sr-only">Loading</p>
      <div className="h-8 w-48 bg-muted" />
      <div className="mt-6 h-24 bg-muted" />
      <div className="mt-3 h-24 bg-muted" />
    </div>
  );
}
