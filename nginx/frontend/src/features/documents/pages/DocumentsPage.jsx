import React from 'react';
import { useNavigate } from 'react-router-dom';
import useDocuments from '../hooks/useDocuments';
import useChunkReport from '../hooks/useChunkReport';
import DocumentList from '../components/DocumentList';
import ChunkReportPanel from '../components/ChunkReportPanel';
import EmptyState from '../../../shared/components/EmptyState';
import ErrorState from '../../../shared/components/ErrorState';
import LoadingSpinner from '../../../shared/components/LoadingSpinner';

export default function DocumentsPage() {
  const nav = useNavigate();
  const { documents, error: loadError, loading } = useDocuments();
  const { report, error: reportError, openReport, closeReport } = useChunkReport();
  const error = loadError || reportError;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner large />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Documents</h1>
          <p className="text-slate-500 mt-1">Manage your uploaded PDF documents</p>
        </div>
        <button onClick={() => nav('/upload')} className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-medium hover:from-blue-700 hover:to-indigo-700 transition-all shadow-lg shadow-blue-200">
          Upload New
        </button>
      </div>

      <ErrorState message={error} />

      {documents.length === 0 ? (
        <EmptyState
          title="No documents yet"
          description="Upload your first PDF document to get started"
          action={<button onClick={() => nav('/upload')} className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-medium hover:from-blue-700 hover:to-indigo-700 transition-all shadow-lg shadow-blue-200">Upload PDF</button>}
        />
      ) : (
        <DocumentList documents={documents} onViewReport={openReport} onChat={(id) => nav(`/chat?docId=${id}`)} />
      )}

      <ChunkReportPanel report={report} onClose={closeReport} />
    </div>
  );
}
