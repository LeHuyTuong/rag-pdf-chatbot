import { useState } from 'react';
import { getChunkReport } from '../api/documentApi';
import { getErrorMessage } from '../../../shared/utils/errors';

export default function useChunkReport() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');

  async function openReport(documentId) {
    try {
      setReport(await getChunkReport(documentId));
      setError('');
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load chunk report.'));
    }
  }

  return { report, error, openReport, closeReport: () => setReport(null), setError };
}
