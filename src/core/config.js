/**
 * GeoVigilant Argus — Core Environment & API Configuration
 */

export const API_BASE_URL = (
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL) ||
  (typeof window !== 'undefined' && window.ARGUS_API_BASE_URL) ||
  ''
).replace(/\/+$/, '');

export function apiUrl(endpoint) {
  if (!endpoint) return '';
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    return endpoint;
  }
  const cleanPath = endpoint.startsWith('/') ? endpoint : '/' + endpoint;
  return API_BASE_URL ? `${API_BASE_URL}${cleanPath}` : cleanPath;
}
