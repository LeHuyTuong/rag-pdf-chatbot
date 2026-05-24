import React from 'react';
import Modal from '../../../shared/components/Modal';

export default function SourceChunkPanel({ report, onClose }) {
  if (!report) return null;

  return (
    <Modal title={report.title} onClose={onClose}>
      <pre className="whitespace-pre-wrap rounded-xl border border-slate-100 bg-slate-50 p-4 font-mono text-xs leading-relaxed text-slate-700">
        {JSON.stringify(report.data, null, 2)}
      </pre>
    </Modal>
  );
}
