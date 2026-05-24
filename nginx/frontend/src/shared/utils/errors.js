export function getErrorMessage(error, fallback = 'Request failed.') {
  if (!error?.response) return fallback;
  return (
    error.response.data?.detail ||
    error.response.data?.message ||
    error.response.data?.error ||
    fallback
  );
}
