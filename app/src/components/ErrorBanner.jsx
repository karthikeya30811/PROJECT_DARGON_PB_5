// Dismissable error banner; renders nothing when there is no message.
export default function ErrorBanner({ message, onClose }) {
  if (!message) return null;
  return (
    <div role="alert" className="my-4 flex items-start justify-between gap-4 rounded border-2 border-red-700 bg-yellow-50 p-4">
      <span className="font-semibold">{message}</span>
      <button
        type="button"
        onClick={onClose}
        className="whitespace-nowrap rounded border-2 border-slate-900 px-3 py-1 font-bold"
      >
        Close
      </button>
    </div>
  );
}
