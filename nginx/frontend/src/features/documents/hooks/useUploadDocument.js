import { useState } from 'react';
import { uploadDocument } from '../api/documentApi';
import { getErrorMessage } from '../../../shared/utils/errors';

/**
 * Hook hỗ trợ upload document trên client.
 * - upload(file): validate file, gọi API, trả về document object hoặc null.
 */
export default function useUploadDocument() {
  const [document, setDocument] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function upload(file) {
    if (!file) {
      setError('Please select a PDF file before uploading.');
      return null;
    }
    setError('');
    setLoading(true);
    try {
      const uploaded = await uploadDocument(file);
      setDocument(uploaded);
      return uploaded;
    } catch (err) {
      setError(getErrorMessage(err, 'Upload failed.'));
      return null;
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setDocument(null);
    setError('');
  }

  return { document, error, loading, upload, reset, setError };
}
