import React from 'react';
import Modal from '../../../shared/components/Modal';

/**
 * Hiển thị chunk report (dùng để debug ingest trên UI).
 * Props:
 * - report: object báo cáo ingest (đã JSON.stringify trong pre).
 * - onClose: callback đóng modal.
 */
export default function ChunkReportPanel({ report, onClose }) {
  if (!report) return null;
  return (
    <Modal title="Chunk Report" onClose={onClose}>
      <pre className="text-xs leading-relaxed text-slate-700 whitespace-pre-wrap font-mono bg-slate-50 rounded-xl p-4 border border-slate-100">
        {JSON.stringify(report, null, 2)}
      </pre>
    </Modal>
  );
}
