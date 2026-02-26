import { useEffect, useState } from "react";

interface SyncStatus {
  status: string;
  completed_at: string | null;
  techniques_count: number;
  tactics_count: number;
}

// In production (ACA), VITE_BACKEND_URL is set at build time to the Container App URL.
// In local dev it is empty so relative paths work via the Vite proxy.
const BACKEND = import.meta.env.VITE_BACKEND_URL ?? "";

export function Header() {
  const [sync, setSync] = useState<SyncStatus | null>(null);

  useEffect(() => {
    fetch(`${BACKEND}/api/v1/sync/status`)
      .then((r) => r.json())
      .then(setSync)
      .catch(() => {});
  }, []);

  const statusColor =
    sync?.status === "success"
      ? "bg-green-500"
      : sync?.status === "running"
        ? "bg-yellow-500"
        : sync?.status === "error"
          ? "bg-red-500"
          : "bg-gray-500";

  const lastSync = sync?.completed_at
    ? new Date(sync.completed_at).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Never";

  return (
    <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
      <div className="container mx-auto max-w-7xl flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center text-white font-bold text-sm">
            M
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white leading-none">
              MITRE ATT&amp;CK Threat Analyzer
            </h1>
            <p className="text-xs text-gray-400 mt-0.5">
              AI-powered threat analysis
            </p>
          </div>
        </div>

        {sync && (
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <span
              className={`inline-block w-2 h-2 rounded-full ${statusColor}`}
            />
            <span>
              {sync.techniques_count} techniques &middot; {sync.tactics_count}{" "}
              tactics
            </span>
            <span className="text-gray-600">|</span>
            <span>Synced: {lastSync}</span>
          </div>
        )}
      </div>
    </header>
  );
}
