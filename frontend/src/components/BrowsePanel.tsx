import { useEffect, useState, useCallback } from "react";

// In production (ACA), VITE_BACKEND_URL is set at build time to the Container App URL.
// In local dev it is empty so relative paths work via the Vite proxy.
const BACKEND = import.meta.env.VITE_BACKEND_URL ?? "";

// ── Types ──────────────────────────────────────────────────────────────────

interface Tactic {
  id: number;
  attack_id: string;
  name: string;
  shortname: string;
  description: string | null;
}

interface Technique {
  id: number;
  attack_id: string;
  name: string;
  is_subtechnique: boolean;
  parent_attack_id: string | null;
  tactic_names: string[];
  platforms: string[];
}

interface MitigationBrief {
  attack_id: string;
  name: string;
  relationship_context: string | null;
}

interface TechniqueDetail extends Technique {
  description: string | null;
  detection: string | null;
  data_sources: string[];
  url: string | null;
  subtechnique_ids: string[];
  mitigations: MitigationBrief[];
}

// ── Helpers ────────────────────────────────────────────────────────────────

function Badge({ text }: { text: string }) {
  return (
    <span className="inline-block px-1.5 py-0.5 text-xs bg-gray-700 text-gray-300 rounded">
      {text}
    </span>
  );
}

// ── Detail modal ───────────────────────────────────────────────────────────

function TechniqueModal({
  detail,
  onClose,
}: {
  detail: TechniqueDetail;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-gray-800 border border-gray-600 rounded-lg max-w-2xl w-full max-h-[80vh] overflow-y-auto p-5"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-blue-400 font-mono text-sm font-semibold">
                {detail.attack_id}
              </span>
              {detail.is_subtechnique && (
                <span className="text-xs bg-blue-900 text-blue-300 px-1.5 py-0.5 rounded">
                  sub-technique
                </span>
              )}
            </div>
            <h2 className="text-lg font-semibold text-white mt-1">
              {detail.name}
            </h2>
            <div className="flex flex-wrap gap-1 mt-2">
              {detail.tactic_names.map((t) => (
                <Badge key={t} text={t} />
              ))}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 ml-4 text-xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Description */}
        {detail.description && (
          <section className="mb-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
              Description
            </h3>
            <p className="text-sm text-gray-300 leading-relaxed">
              {detail.description}
            </p>
          </section>
        )}

        {/* Detection */}
        {detail.detection && (
          <section className="mb-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
              Detection
            </h3>
            <p className="text-sm text-gray-300 leading-relaxed">
              {detail.detection}
            </p>
          </section>
        )}

        {/* Platforms & Data Sources */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          {detail.platforms.length > 0 && (
            <section>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
                Platforms
              </h3>
              <div className="flex flex-wrap gap-1">
                {detail.platforms.map((p) => (
                  <Badge key={p} text={p} />
                ))}
              </div>
            </section>
          )}
          {detail.data_sources.length > 0 && (
            <section>
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
                Data Sources
              </h3>
              <div className="flex flex-wrap gap-1">
                {detail.data_sources.slice(0, 4).map((d) => (
                  <Badge key={d} text={d} />
                ))}
                {detail.data_sources.length > 4 && (
                  <Badge text={`+${detail.data_sources.length - 4} more`} />
                )}
              </div>
            </section>
          )}
        </div>

        {/* Sub-techniques */}
        {detail.subtechnique_ids.length > 0 && (
          <section className="mb-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
              Sub-techniques ({detail.subtechnique_ids.length})
            </h3>
            <div className="flex flex-wrap gap-1">
              {detail.subtechnique_ids.map((id) => (
                <span
                  key={id}
                  className="text-xs font-mono text-blue-400 bg-blue-950 px-1.5 py-0.5 rounded"
                >
                  {id}
                </span>
              ))}
            </div>
          </section>
        )}

        {/* Mitigations */}
        {detail.mitigations.length > 0 && (
          <section className="mb-4">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Mitigations ({detail.mitigations.length})
            </h3>
            <div className="space-y-2">
              {detail.mitigations.map((m) => (
                <div
                  key={m.attack_id}
                  className="bg-gray-750 border border-gray-700 rounded p-2.5"
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono text-green-400">
                      {m.attack_id}
                    </span>
                    <span className="text-sm text-gray-200 font-medium">
                      {m.name}
                    </span>
                  </div>
                  {m.relationship_context && (
                    <p className="text-xs text-gray-400 leading-relaxed">
                      {m.relationship_context}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Link */}
        {detail.url && (
          <a
            href={detail.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-400 hover:text-blue-300 underline"
          >
            View on MITRE ATT&CK
          </a>
        )}
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export function BrowsePanel() {
  const [tactics, setTactics] = useState<Tactic[]>([]);
  const [expandedTactic, setExpandedTactic] = useState<number | null>(null);
  const [tacticTechniques, setTacticTechniques] = useState<
    Record<number, Technique[]>
  >({});
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Technique[] | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [selectedDetail, setSelectedDetail] = useState<TechniqueDetail | null>(
    null
  );
  const [loadingDetail, setLoadingDetail] = useState<string | null>(null);

  // Load tactics on mount
  useEffect(() => {
    fetch(`${BACKEND}/api/v1/tactics`)
      .then((r) => r.json())
      .then(setTactics)
      .catch(console.error);
  }, []);

  // Toggle tactic expansion and lazy-load its techniques
  const toggleTactic = useCallback(
    async (tacticId: number) => {
      if (expandedTactic === tacticId) {
        setExpandedTactic(null);
        return;
      }
      setExpandedTactic(tacticId);
      if (!tacticTechniques[tacticId]) {
        const data = await fetch(
          `${BACKEND}/api/v1/tactics/${tacticId}/techniques`
        ).then((r) => r.json());
        setTacticTechniques((prev) => ({ ...prev, [tacticId]: data }));
      }
    },
    [expandedTactic, tacticTechniques]
  );

  // Keyword search with debounce
  useEffect(() => {
    if (!searchQuery || searchQuery.length < 2) {
      setSearchResults(null);
      return;
    }
    const timer = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const data = await fetch(
          `${BACKEND}/api/v1/techniques/search?q=${encodeURIComponent(searchQuery)}`
        ).then((r) => r.json());
        setSearchResults(data);
      } finally {
        setSearchLoading(false);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Load technique detail
  const openDetail = useCallback(async (attackId: string) => {
    setLoadingDetail(attackId);
    try {
      const data = await fetch(
        `${BACKEND}/api/v1/techniques/${attackId}`
      ).then((r) => r.json());
      setSelectedDetail(data);
    } finally {
      setLoadingDetail(null);
    }
  }, []);

  // ── Render helpers ────────────────────────────────────────────────────────

  const TechniqueRow = ({ t }: { t: Technique }) => (
    <button
      onClick={() => openDetail(t.attack_id)}
      disabled={loadingDetail === t.attack_id}
      className={`w-full text-left px-3 py-1.5 rounded hover:bg-gray-700 transition-colors flex items-center gap-2 group ${
        t.is_subtechnique ? "pl-6" : ""
      }`}
    >
      <span className="text-xs font-mono text-blue-400 w-20 shrink-0">
        {t.attack_id}
      </span>
      <span className="text-sm text-gray-300 group-hover:text-white truncate">
        {t.name}
      </span>
      {loadingDetail === t.attack_id && (
        <span className="ml-auto text-xs text-gray-500">...</span>
      )}
    </button>
  );

  return (
    <>
      <div className="flex flex-col bg-gray-800 rounded-lg border border-gray-700 overflow-hidden h-[calc(100vh-10rem)]">
        {/* Panel header */}
        <div className="px-4 py-3 border-b border-gray-700 flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500" />
          <h2 className="text-sm font-semibold text-gray-200">
            ATT&amp;CK Knowledge Base
          </h2>
          <span className="ml-auto text-xs text-gray-500">
            {tactics.length} tactics
          </span>
        </div>

        {/* Search */}
        <div className="px-3 py-2 border-b border-gray-700">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search techniques..."
            className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-2 py-2">
          {/* Search results */}
          {searchQuery.length >= 2 ? (
            <div>
              <p className="text-xs text-gray-500 px-2 mb-2">
                {searchLoading
                  ? "Searching..."
                  : `${searchResults?.length ?? 0} results for "${searchQuery}"`}
              </p>
              {searchResults?.map((t) => (
                <TechniqueRow key={t.id} t={t} />
              ))}
              {!searchLoading && searchResults?.length === 0 && (
                <p className="text-xs text-gray-600 px-2">No matches found.</p>
              )}
            </div>
          ) : (
            /* Tactics accordion */
            <div className="space-y-0.5">
              {tactics.map((tac) => (
                <div key={tac.id}>
                  <button
                    onClick={() => toggleTactic(tac.id)}
                    className="w-full text-left px-3 py-2 rounded hover:bg-gray-700 transition-colors flex items-center gap-2"
                  >
                    <span
                      className={`text-gray-500 text-xs w-3 transition-transform ${
                        expandedTactic === tac.id ? "rotate-90" : ""
                      }`}
                    >
                      &#9654;
                    </span>
                    <span className="text-xs font-mono text-gray-400 w-16 shrink-0">
                      {tac.attack_id}
                    </span>
                    <span className="text-sm text-gray-200 font-medium">
                      {tac.name}
                    </span>
                  </button>

                  {expandedTactic === tac.id && (
                    <div className="ml-2 mt-0.5 mb-1 border-l border-gray-700 pl-1">
                      {!tacticTechniques[tac.id] ? (
                        <p className="text-xs text-gray-600 px-3 py-1">
                          Loading...
                        </p>
                      ) : tacticTechniques[tac.id].length === 0 ? (
                        <p className="text-xs text-gray-600 px-3 py-1">
                          No techniques.
                        </p>
                      ) : (
                        tacticTechniques[tac.id].map((t) => (
                          <TechniqueRow key={t.id} t={t} />
                        ))
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Technique detail modal */}
      {selectedDetail && (
        <TechniqueModal
          detail={selectedDetail}
          onClose={() => setSelectedDetail(null)}
        />
      )}
    </>
  );
}
