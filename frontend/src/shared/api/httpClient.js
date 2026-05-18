import axios from 'axios';

/**
 * HTTP client chung cho frontend.
 *
 * - Thiết lập `baseURL` từ env `VITE_API_BASE_URL` (fallback localhost).
 * - Thêm Authorization header nếu có token.
 * - Interceptor response: nếu 401/403 thì redirect về /login.
 */

const httpClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080',
});

httpClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

httpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const path = window.location.pathname;
    if ((status === 401 || status === 403) && path !== '/login') {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default httpClient;
