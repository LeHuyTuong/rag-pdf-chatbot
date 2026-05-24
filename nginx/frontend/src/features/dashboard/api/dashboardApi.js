import httpClient from '../../../shared/api/httpClient';

export async function getDashboard() {
  const response = await httpClient.get('/api/dashboard');
  return response.data;
}
