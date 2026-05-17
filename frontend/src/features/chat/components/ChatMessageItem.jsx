import React from 'react';

export default function ChatMessageItem({ message, onOpenReport }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
      <div className={`max-w-[85%] lg:max-w-[70%] ${isUser ? 'message-bubble-user' : 'message-bubble-assistant'}`}>
        <div className="px-4 py-3">
          <p className={`text-sm leading-relaxed whitespace-pre-wrap ${isUser ? 'text-white' : 'text-slate-700'}`}>
            {message.content}
          </p>
        </div>
        {message.sourcesJson && (
          <div className="px-4 pb-3">
            <details className="text-xs">
              <summary className={`cursor-pointer font-medium ${isUser ? 'text-blue-200' : 'text-blue-600'} hover:opacity-80`}>View Sources</summary>
              <pre className={`mt-2 p-2 rounded-lg text-xs overflow-auto max-h-32 ${isUser ? 'bg-white/10 text-blue-100' : 'bg-slate-50 text-slate-600'}`}>
                {message.sourcesJson}
              </pre>
            </details>
          </div>
        )}
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
