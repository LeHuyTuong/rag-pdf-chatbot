import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useUploadDocument from '../hooks/useUploadDocument';
import UploadDocumentForm from '../components/UploadDocumentForm';
import ErrorState from '../../../shared/components/ErrorState';

export default function UploadPage() {
  const [file, setFile] = useState(null);
  const { document, error, loading, upload, reset } = useUploadDocument();
  const nav = useNavigate();

  async function handleUpload() {
    await upload(file);
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Upload PDF</h1>
        <p className="text-slate-500 mt-1">Upload a PDF document to start asking questions</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <UploadDocumentForm file={file} setFile={setFile} loading={loading} onUpload={handleUpload} />
        <div className="lg:col-span-2">
          <div className="bg-white rounded-2xl border border-slate-100 p-5 space-y-4">
            <h3 className="font-semibold text-slate-800">Upload Instructions</h3>
            <ul className="space-y-3">
              {['Select or drag a PDF file into the upload area', 'Click Upload Document to process your file', 'The system will extract text and create chunks for Q&A', 'Once processed, you can chat with your document'].map((item, index) => (
                <li key={item} className="flex items-start gap-3 text-sm text-slate-600">
                  <span className="w-6 h-6 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">{index + 1}</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <ErrorState message={error} />

      {document && (
        <div className="animate-fade-in">
          <div className="bg-white rounded-2xl border border-emerald-100 p-6">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center shrink-0">
                <span className="text-emerald-600 font-bold">OK</span>
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-slate-800">Upload Finished</h3>
                <p className="text-sm text-slate-500 mt-1">{document.totalPages} pages · {document.totalChunks} chunks · {document.status}</p>
                {document.errorMessage && <p className="text-sm text-red-600 mt-2">{document.errorMessage}</p>}
                <div className="flex gap-3 mt-4">
                  <button onClick={() => nav(`/chat?docId=${document.id}`)} className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-medium hover:from-blue-700 hover:to-indigo-700 transition-all shadow-sm shadow-blue-200">
                    Start Chatting
                  </button>
                  <button onClick={() => { reset(); setFile(null); }} className="flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-200 text-slate-600 text-sm font-medium hover:bg-slate-50 transition-all">
                    Upload Another
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
