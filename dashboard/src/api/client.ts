import axios from 'axios';

const client = axios.create({
  baseURL: '/api',
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
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
