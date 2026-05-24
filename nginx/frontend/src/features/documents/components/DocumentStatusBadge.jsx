import React from 'react';

export default function DocumentStatusBadge({ status }) {
  const statusMap = {
    completed: 'badge badge-success',
    processing: 'badge badge-warning',
    failed: 'badge badge-error',
    uploaded: 'badge badge-info',
    file_missing: 'badge badge-error',
  };

  return (
    <span className={statusMap[status] || 'badge badge-info'}>
      <span className={`w-1.5 h-1.5 rounded-full ${status === 'completed' ? 'bg-green-500' : status === 'processing' ? 'bg-amber-500' : status === 'failed' || status === 'file_missing' ? 'bg-red-500' : 'bg-blue-500'}`} />
      {status === 'file_missing' ? 'file missing' : status}
    </span>
  );
}
