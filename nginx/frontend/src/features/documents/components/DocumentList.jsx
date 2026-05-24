import React from 'react';
import DocumentCard from './DocumentCard';

export default function DocumentList({ documents, onViewReport, onChat }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {documents.map((doc) => (
        <DocumentCard key={doc.id} doc={doc} onViewReport={onViewReport} onChat={onChat} />
      ))}
    </div>
  );
}
