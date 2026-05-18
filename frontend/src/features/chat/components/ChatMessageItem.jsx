import React from 'react';

function parseSources(sourcesJson) {
  if (!sourcesJson) return [];
  try {
    const parsed = JSON.parse(sourcesJson);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function formatScore(score) {
  const numeric = Number(score);
  if (!Number.isFinite(numeric)) return 'n/a';
  return numeric.toFixed(2);
}

function SourceCards({ sources, rawJson, isUser }) {
  if (!sources.length && !rawJson) return null;

  return (
    <div className="px-4 pb-3 space-y-2">
      {sources.length > 0 && (
        <div className="space-y-2">
          <div className={`text-[11px] font-semibold uppercase tracking-wide ${isUser ? 'text-blue-100' : 'text-slate-500'}`}>
            Sources
          </div>
          <div className="grid gap-2">
            {sources.map((source, index) => (
              <div key={`${source.chunk_id || 'source'}-${index}`} className={`rounded-lg border p-3 text-xs ${isUser ? 'border-white/15 bg-white/10 text-blue-50' : 'border-slate-100 bg-slate-50 text-slate-600'}`}>
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span className={`font-semibold ${isUser ? 'text-white' : 'text-slate-700'}`}>{source.file_name || 'Unknown file'}</span>
                  <span>p. {source.page_start ?? '?'}-{source.page_end ?? source.page_start ?? '?'}</span>
                  <span>score {formatScore(source.score)}</span>
                  <span className={`rounded px-1.5 py-0.5 font-medium ${source.support_level === 'strong' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                    {source.support_level || 'medium'}
                  </span>
                </div>
                {source.preview && (
                  <p className={`mt-2 max-h-16 overflow-hidden leading-relaxed ${isUser ? 'text-blue-50/90' : 'text-slate-500'}`}>
                    {source.preview}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {rawJson && (
        <details className="text-xs">
          <summary className={`cursor-pointer font-medium ${isUser ? 'text-blue-200' : 'text-blue-600'} hover:opacity-80`}>
            Raw source JSON
          </summary>
          <pre className={`mt-2 max-h-32 overflow-auto rounded-lg p-2 text-xs ${isUser ? 'bg-white/10 text-blue-100' : 'bg-slate-100 text-slate-600'}`}>
            {rawJson}
          </pre>
        </details>
      )}
    </div>
  );
}

export default function ChatMessageItem({ message, onOpenReport }) {
  const isUser = message.role === 'user';
  const sources = parseSources(message.sourcesJson);

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
      <div className={`max-w-[85%] lg:max-w-[70%] ${isUser ? 'message-bubble-user' : 'message-bubble-assistant'}`}>
        <div className="px-4 py-3">
          <p className={`text-sm leading-relaxed whitespace-pre-wrap ${isUser ? 'text-white' : 'text-slate-700'}`}>
            {message.content}
          </p>
        </div>
        <SourceCards sources={sources} rawJson={message.sourcesJson} isUser={isUser} />
        {message.id && message.role === 'assistant' && (
          <div className="px-4 pb-3 flex gap-2 justify-start">
            <button onClick={() => onOpenReport(message.id, 'retrieval')} className="text-[11px] px-2.5 py-1 rounded-lg font-medium transition-all bg-slate-100 text-slate-500 hover:bg-slate-200">
              Retrieval
            </button>
            <button onClick={() => onOpenReport(message.id, 'answer')} className="text-[11px] px-2.5 py-1 rounded-lg font-medium transition-all bg-slate-100 text-slate-500 hover:bg-slate-200">
              Answer
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
