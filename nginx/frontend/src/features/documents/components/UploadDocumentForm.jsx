import React, { useCallback, useRef, useState } from 'react';
import LoadingSpinner from '../../../shared/components/LoadingSpinner';

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * Component form upload PDF.
 * Ghi chú:
 * - Validate MIME type `application/pdf` trên client (không thay thế validate server).
 * - Kéo thả hoặc click để chọn file; hiển thị preview tên và kích thước.
 *
 * Props:
 * - file: File được chọn
 * - setFile: setter để cập nhật file
 * - loading: trạng thái đang upload
 * - onUpload: hàm gọi khi nhấn upload
 */
export default function UploadDocumentForm({ file, setFile, loading, onUpload }) {
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef(null);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.type === 'application/pdf') setFile(droppedFile);
  }, [setFile]);

  return (
    <div className="lg:col-span-3 space-y-4">
      <div className={`upload-zone ${dragging ? 'dragging' : ''}`} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop} onClick={() => fileInputRef.current?.click()}>
        <input ref={fileInputRef} type="file" accept="application/pdf" onChange={(e) => e.target.files[0] && setFile(e.target.files[0])} className="hidden" />
        {file ? (
          <div className="space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-blue-50 flex items-center justify-center mx-auto">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-8 h-8 text-blue-600">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            </div>
            <div>
              <p className="font-semibold text-slate-700">{file.name}</p>
              <p className="text-sm text-slate-400 mt-0.5">{formatFileSize(file.size)}</p>
            </div>
            <button onClick={(e) => { e.stopPropagation(); setFile(null); }} className="text-sm text-red-500 hover:text-red-600 font-medium">
              Remove file
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-8 h-8 text-slate-400">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <div>
              <p className="font-semibold text-slate-600"><span className="text-blue-600">Click to browse</span> or drag and drop</p>
              <p className="text-sm text-slate-400 mt-1">PDF files only, up to 50MB</p>
            </div>
          </div>
        )}
      </div>

      <button onClick={onUpload} disabled={!file || loading} className="w-full flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-medium text-sm hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-blue-200">
        {loading ? <><LoadingSpinner />Uploading...</> : 'Upload Document'}
      </button>
    </div>
  );
}
