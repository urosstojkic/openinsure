import axios from 'axios';

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
});

client.interceptors.request.use((config) => {
  const role = localStorage.getItem('openinsure_role');
  if (role) {
    config.headers['X-User-Role'] = role;
  }
  // API key for dev/testing — in production, nginx injects this header server-side
  const apiKey = import.meta.env.VITE_API_KEY;
  if (apiKey) {
    config.headers['X-API-Key'] = apiKey;
  }
  return config;
});

client.interceptors.response.use(
  (res) => res,
  (error) => {
    const message =
      error.response?.data?.detail ?? error.message ?? 'Unknown error';
    console.error('[API]', message);
    return Promise.reject(error);
  },
);

export default client;
