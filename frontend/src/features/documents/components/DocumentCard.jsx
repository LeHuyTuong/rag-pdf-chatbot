import React from 'react';
import DocumentStatusBadge from './DocumentStatusBadge';

export default function DocumentCard({ doc, onViewReport, onChat }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-100 p-5 card-hover animate-fade-in">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center shrink-0">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5 text-blue-600">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
            </svg>
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-slate-800 truncate">{doc.originalFileName}</p>
            <p className="text-xs text-slate-400 mt-0.5">{doc.totalPages} pages &middot; {doc.totalChunks} chunks</p>
            {(doc.status === 'failed' || doc.status === 'file_missing') && doc.errorMessage && (
              <p className="text-xs text-red-600 mt-1 line-clamp-2">{doc.errorMessage}</p>
            )}
          </div>
        </div>
        <DocumentStatusBadge status={doc.status} />
      </div>

      <div className="flex gap-2 mt-4 pt-3 border-t border-slate-50">
        <button onClick={() => onChat(doc.id)} className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl bg-gradient-to-r from-blue-500 to-indigo-500 text-white text-sm font-medium hover:from-blue-600 hover:to-indigo-600 transition-all shadow-sm shadow-blue-200">
          Chat
        </button>
        <button onClick={() => onViewReport(doc.id)} className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50 transition-all">
          Chunk Report
        </button>
      </div>
    </div>
  );
}
