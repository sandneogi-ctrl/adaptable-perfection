import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 120000,  // 2 minutes — Yahoo Finance batch fetch can take 30-60s
});

export const stocksApi = {
  getTopGainers:   (limit = 10) => api.get(`/api/top-gainers?limit=${limit}`).then(r => r.data),
  getTopLosers:    (limit = 10) => api.get(`/api/top-losers?limit=${limit}`).then(r => r.data),
  getAllStocks:     ()           => api.get('/api/all-stocks').then(r => r.data),
  getMarketSummary:()           => api.get('/api/market-summary').then(r => r.data),
  refresh:         ()           => api.post('/api/refresh').then(r => r.data),
  getNiftyIndex:   ()           => api.get('/api/nifty-index').then(r => r.data),
};
