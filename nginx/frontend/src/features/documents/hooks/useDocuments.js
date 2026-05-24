import { useEffect, useState } from 'react';
import { getDocuments } from '../api/documentApi';
import { getErrorMessage } from '../../../shared/utils/errors';

/**
 * Hook tải danh sách documents của user hiện tại.
 * Trả về: { documents, error, loading, reload }
 */
export default function useDocuments() {
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      setDocuments(await getDocuments());
      setError('');
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to load documents.'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return { documents, error, loading, reload: load, setError };
}
