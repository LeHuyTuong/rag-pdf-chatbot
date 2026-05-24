import React from 'react';

export default function ChatSessionSidebar({ documents, selectedDocumentId, onSelectDocument, onNewChat, hasChat }) {
  return (
    <aside className="w-full lg:w-72 bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden shrink-0">
      <div className="p-4 border-b border-slate-100">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Documents</h2>
            <p className="text-xs text-slate-400 mt-0.5">Choose one document to chat with</p>
          </div>
          {hasChat && (
            <button onClick={onNewChat} className="px-2.5 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-600 hover:bg-slate-50">
              New
            </button>
          )}
        </div>
      </div>

      <div className="max-h-72 lg:max-h-[calc(100vh-15rem)] overflow-y-auto p-2">
        {documents.length === 0 ? (
          <p className="p-3 text-sm text-slate-400">No documents available.</p>
        ) : (
          documents.map((document) => (
            <button
              key={document.id}
              onClick={() => onSelectDocument(document.id)}
              className={`w-full text-left p-3 rounded-xl transition-all ${
                selectedDocumentId === document.id ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <p className="text-sm font-medium truncate">{document.originalFileName}</p>
              <p className="text-xs opacity-70 mt-1">{document.totalPages || 0} pages / {document.totalChunks || 0} chunks</p>
            </button>
          ))
        )}
      </div>
    </aside>
  );
}
