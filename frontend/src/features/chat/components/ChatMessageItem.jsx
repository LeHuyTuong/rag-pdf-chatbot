import React from 'react';

function parseSourcePayload(sourcesJson) {
  const empty = { sources: [], relatedChunks: [], suggestedQuestions: [], answerType: 'answered', confidence: null };
  if (!sourcesJson) return empty;
  try {
    const parsed = JSON.parse(sourcesJson);
    if (Array.isArray(parsed)) {
      return { ...empty, sources: parsed };
    }
    return {
      sources: Array.isArray(parsed.sources) ? parsed.sources : [],
      relatedChunks: Array.isArray(parsed.related_chunks) ? parsed.related_chunks : [],
      suggestedQuestions: Array.isArray(parsed.suggested_questions) ? parsed.suggested_questions : [],
      answerType: parsed.answer_type || 'answered',
      confidence: parsed.confidence ?? null,
    };
  } catch {
    return empty;
  }
}

function parseJsonArray(value) {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
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

function supportClass(level) {
  if (level === 'strong') return 'bg-emerald-100 text-emerald-700';
  if (level === 'medium') return 'bg-blue-100 text-blue-700';
  return 'bg-amber-100 text-amber-700';
}

function SourceList({ title, sources, isUser, answerType }) {
  if (!sources.length) return null;
  const partial = answerType === 'partial_answer';

  return (
    <div className="space-y-2">
      <div className={`text-[11px] font-semibold uppercase tracking-wide ${isUser ? 'text-blue-100' : 'text-slate-500'}`}>
        {title}
      </div>
      <div className="grid gap-2">
        {sources.map((source, index) => (
          <div key={`${source.chunk_id || title}-${index}`} className={`rounded-lg border p-3 text-xs ${isUser ? 'border-white/15 bg-white/10 text-blue-50' : 'border-slate-100 bg-slate-50 text-slate-600'}`}>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className={`font-semibold ${isUser ? 'text-white' : 'text-slate-700'}`}>{source.file_name || 'Unknown file'}</span>
              <span>p. {source.page_start ?? '?'}-{source.page_end ?? source.page_start ?? '?'}</span>
              <span>score {formatScore(source.score)}</span>
              <span className={`rounded px-1.5 py-0.5 font-medium ${partial ? 'bg-blue-100 text-blue-700' : supportClass(source.support_level)}`}>
                {partial ? 'medium confidence' : (source.support_level || 'medium')}
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
  );
}

function SourceCards({ payload, rawJson, isUser, debugMode }) {
  const { sources, relatedChunks, answerType } = payload;
  const insufficient = answerType === 'insufficient_context';
  const outOfScope = answerType === 'out_of_scope';
  const partial = answerType === 'partial_answer';
  const visibleRawJson = debugMode && rawJson;
  if (!sources.length && !relatedChunks.length && !visibleRawJson && !insufficient && !outOfScope) return null;

  return (
    <div className="px-4 pb-3 space-y-2">
      {insufficient || outOfScope ? (
        <div className={`rounded-lg border px-3 py-2 text-xs ${isUser ? 'border-white/15 bg-white/10 text-blue-50' : 'border-amber-100 bg-amber-50 text-amber-800'}`}>
          {outOfScope ? 'The question appears to be outside the current documents.' : 'No reliable source found in the current documents.'}
        </div>
      ) : (
        <SourceList title={partial ? 'Sources (medium confidence)' : 'Sources'} sources={sources} isUser={isUser} answerType={answerType} />
      )}

      {(insufficient || outOfScope) && relatedChunks.length > 0 && (
        <details className="text-xs">
          <summary className={`cursor-pointer font-medium ${isUser ? 'text-blue-100' : 'text-slate-600'} hover:opacity-80`}>
            Related but insufficient chunks
          </summary>
          <div className="mt-2">
            <SourceList title="Related chunks" sources={relatedChunks} isUser={isUser} answerType={answerType} />
          </div>
        </details>
      )}

      {visibleRawJson && (
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

function SuggestedQuestions({ questions, isUser, onSelect }) {
  if (!questions.length || isUser) return null;
  return (
    <div className="px-4 pb-3">
      <div className="flex flex-wrap gap-2">
        {questions.map((item, index) => (
          <button
            key={`${item}-${index}`}
            type="button"
            onClick={() => onSelect?.(item)}
            className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-left text-xs font-medium text-slate-600 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
          >
            {item}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function ChatMessageItem({ message, onOpenReport, onSuggestedQuestion, debugMode = false }) {
  const isUser = message.role === 'user';
  const sourcePayload = parseSourcePayload(message.sourcesJson);
  const explicitRelated = parseJsonArray(message.relatedChunksJson);
  const explicitSuggested = parseJsonArray(message.suggestedQuestionsJson);
  const payload = {
    ...sourcePayload,
    relatedChunks: explicitRelated.length ? explicitRelated : sourcePayload.relatedChunks,
    suggestedQuestions: explicitSuggested.length ? explicitSuggested : sourcePayload.suggestedQuestions,
    answerType: message.answerType || sourcePayload.answerType,
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
      <div className={`max-w-[85%] lg:max-w-[70%] ${isUser ? 'message-bubble-user' : 'message-bubble-assistant'}`}>
        <div className="px-4 py-3">
          <p className={`text-sm leading-relaxed whitespace-pre-wrap ${isUser ? 'text-white' : 'text-slate-700'}`}>
            {message.content}
          </p>
        </div>
        <SourceCards payload={payload} rawJson={message.sourcesJson} isUser={isUser} debugMode={debugMode} />
        <SuggestedQuestions questions={payload.suggestedQuestions} isUser={isUser} onSelect={onSuggestedQuestion} />
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
