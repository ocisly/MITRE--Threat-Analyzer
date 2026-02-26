import { useState, useRef, useEffect, useCallback } from "react";

// ── AG-UI SSE event types ──────────────────────────────────────────────────

interface AgUiEvent {
  type: string;
  delta?: string;
  messageId?: string;
  toolCallId?: string;
  toolCallName?: string;
  toolCallArgs?: string;
  role?: string;
}

// ── Message model ──────────────────────────────────────────────────────────

type MessageRole = "user" | "assistant";

interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  toolCalls?: ToolCall[];
  streaming?: boolean;
}

interface ToolCall {
  id: string;
  name: string;
  done: boolean;
  startedAt: number;
  durationMs?: number;
}

// ── Markdown-lite renderer (bold + code only) ──────────────────────────────

function renderMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" class="text-blue-400 underline">$1</a>')
    .replace(/^### (.+)$/gm, '<p class="font-semibold text-gray-200 mt-3 mb-1">$1</p>')
    .replace(/^## (.+)$/gm, '<p class="font-bold text-white text-base mt-4 mb-1">$1</p>')
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
    .replace(/\n/g, "<br/>");
}

// ── Tool call badge ────────────────────────────────────────────────────────

const TOOL_LABEL: Record<string, string> = {
  search_techniques: "Searching techniques",
  get_technique_detail: "Getting technique detail",
  get_all_tactics: "Listing tactics",
  find_mitigations: "Finding mitigations",
};

function ToolBadge({ call }: { call: ToolCall }) {
  return (
    <div className="flex items-center gap-2 text-xs text-gray-400 bg-gray-700/50 rounded px-2 py-1 my-1">
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${call.done ? "bg-green-500" : "bg-yellow-400 animate-pulse"}`} />
      <span className="font-mono">{TOOL_LABEL[call.name] ?? call.name}</span>
      {call.done && (
        <span className="text-green-500 ml-auto">
          {call.durationMs !== undefined ? `Done in ${(call.durationMs / 1000).toFixed(1)}s` : "Done"}
        </span>
      )}
    </div>
  );
}

// Merge consecutive same-named tool calls into a single display entry.
function mergeToolCalls(calls: ToolCall[]): { call: ToolCall; count: number }[] {
  return calls.reduce<{ call: ToolCall; count: number }[]>((acc, tc) => {
    const last = acc[acc.length - 1];
    if (last && last.call.name === tc.name) {
      last.count++;
      // keep the latest status; use the longest observed duration
      last.call = {
        ...last.call,
        done: last.call.done || tc.done,
        durationMs:
          tc.durationMs !== undefined
            ? Math.max(last.call.durationMs ?? 0, tc.durationMs)
            : last.call.durationMs,
      };
      return acc;
    }
    return [...acc, { call: tc, count: 1 }];
  }, []);
}

// ── Message bubble ─────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-gray-700 text-gray-200"
        }`}
      >
        {/* Tool calls */}
        {msg.toolCalls && msg.toolCalls.length > 0 && (
          <div className="mb-2">
            {mergeToolCalls(msg.toolCalls).map(({ call }) => (
              <ToolBadge key={call.id} call={call} />
            ))}
          </div>
        )}
        {/* Message content */}
        {msg.content && (
          <div
            dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
          />
        )}
        {msg.streaming && !msg.content && (
          <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse rounded" />
        )}
      </div>
    </div>
  );
}

// In production (ACA), VITE_BACKEND_URL is set at build time to the Container App URL.
// In local dev it is empty so relative paths work via the Vite proxy.
const BACKEND = import.meta.env.VITE_BACKEND_URL ?? "";

// ── Main component ─────────────────────────────────────────────────────────

export function ThreatAnalyzer() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || running) return;

    // Add user message
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setRunning(true);

    // Build conversation history for the AG-UI request
    const allMessages = [...messages, userMsg].map((m) => ({
      role: m.role,
      content: m.content,
    }));

    // Placeholder assistant message
    const assistantId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: "", streaming: true, toolCalls: [] },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch(`${BACKEND}/agent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: allMessages }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw || raw === "[DONE]") continue;

          let evt: AgUiEvent;
          try {
            evt = JSON.parse(raw);
          } catch {
            continue;
          }

          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantId) return m;
              switch (evt.type) {
                case "TEXT_MESSAGE_CONTENT":
                  return { ...m, content: m.content + (evt.delta ?? "") };
                case "TOOL_CALL_START":
                  return {
                    ...m,
                    toolCalls: [
                      ...(m.toolCalls ?? []),
                      { id: evt.toolCallId ?? crypto.randomUUID(), name: evt.toolCallName ?? "", done: false, startedAt: Date.now() },
                    ],
                  };
                case "TOOL_CALL_END":
                  return {
                    ...m,
                    toolCalls: (m.toolCalls ?? []).map((tc) =>
                      tc.id === evt.toolCallId ? { ...tc, done: true, durationMs: Date.now() - tc.startedAt } : tc
                    ),
                  };
                case "RUN_FINISHED":
                  return {
                    ...m,
                    streaming: false,
                    toolCalls: (m.toolCalls ?? []).map((tc) =>
                      tc.done ? tc : { ...tc, done: true, durationMs: Date.now() - tc.startedAt }
                    ),
                  };
                default:
                  return m;
              }
            })
          );
        }
      }

      // Stream closed — finalize any tool calls not already marked done
      // (covers cases where RUN_FINISHED or TOOL_CALL_END were never sent)
      const streamEndTime = Date.now();
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== assistantId) return m;
          return {
            ...m,
            streaming: false,
            toolCalls: (m.toolCalls ?? []).map((tc) =>
              tc.done ? tc : { ...tc, done: true, durationMs: streamEndTime - tc.startedAt }
            ),
          };
        })
      );
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `Error: ${err.message}`, streaming: false }
              : m
          )
        );
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }, [input, messages, running]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const stopStreaming = () => {
    abortRef.current?.abort();
    setRunning(false);
  };

  return (
    <div className="flex flex-col bg-gray-800 rounded-lg border border-gray-700 overflow-hidden h-[calc(100vh-10rem)]">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700 flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-blue-500" />
        <h2 className="text-sm font-semibold text-gray-200">
          AI Threat Analysis
        </h2>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 text-sm mt-8 px-4">
            <p className="text-gray-400 font-medium mb-2">
              Describe the attack symptoms you observed
            </p>
            <p className="text-xs leading-relaxed">
              Example: <em>"We found unusual outbound network traffic at 3am, an admin account logged in from an unknown IP, and several shared files appear to be encrypted."</em>
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-3 py-3 border-t border-gray-700 flex gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe observed attack symptoms... (Enter to send, Shift+Enter for newline)"
          disabled={running}
          rows={2}
          className="flex-1 bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 resize-none disabled:opacity-50"
        />
        {running ? (
          <button
            onClick={stopStreaming}
            className="px-3 py-2 bg-red-700 hover:bg-red-600 text-white text-sm rounded transition-colors self-end"
          >
            Stop
          </button>
        ) : (
          <button
            onClick={sendMessage}
            disabled={!input.trim()}
            className="px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded transition-colors self-end disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
}
