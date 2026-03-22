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
