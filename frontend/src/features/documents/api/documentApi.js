import httpClient from '../../../shared/api/httpClient';

export async function getDocuments() {
  const response = await httpClient.get('/api/documents');
  return response.data;
}

export async function uploadDocument(file) {
  const body = new FormData();
  body.append('file', file);
  const response = await httpClient.post('/api/documents/upload', body);
  return response.data;
}

export async function getChunkReport(documentId) {
  const response = await httpClient.get(`/api/documents/${documentId}/chunk-report`);
  return response.data;
}
