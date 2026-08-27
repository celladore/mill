/**
 * Centralized API client for Mill Converter
 *
 * Provides consistent error handling, request/response interceptors,
 * and centralized configuration for all API calls.
 *
 * TODO: Production enhancements:
 * - Add request retry logic with exponential backoff
 * - Implement request cancellation (AbortController)
 * - Add request/response logging for debugging
 * - Implement request queuing for rate limiting
 * - Add offline detection and queuing
 */

import axios from 'axios';
import { clearMystiraUser, getMystiraAccessToken } from '../auth/mystiraOidcInstance';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
const API_BASE = `${BACKEND_URL}/api`;

// Create axios instance with default configuration
const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 300000, // 5 minutes for large file conversions
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
apiClient.interceptors.request.use(
  async config => {
    // Add request ID for tracking
    config.headers['X-Request-ID'] = crypto.randomUUID();

    // Access tokens are issued by Mystira Identity through Authorization Code
    // + PKCE. Never fall back to the retired localStorage mock token.
    const token = await getMystiraAccessToken();
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }

    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  response => {
    return response;
  },
  error => {
    // Centralized error handling
    if (error.response) {
      // Server responded with error status
      const { status, data } = error.response;

      switch (status) {
        case 400:
          // Bad request - validation errors
          return Promise.reject({
            type: 'validation_error',
            message: data.detail || 'Invalid request',
            errors: data.errors || [],
            status,
          });
        case 401:
          // Unauthorized - redirect to login
          clearMystiraUser().catch(clearError => {
            console.error('[MystiraOidc] Failed to clear rejected user:', clearError);
          });
          return Promise.reject({
            type: 'authentication_error',
            message: 'Authentication required',
            status,
          });
        case 403:
          // Forbidden
          return Promise.reject({
            type: 'authorization_error',
            message: data.detail || 'Access denied',
            status,
          });
        case 404:
          // Not found
          return Promise.reject({
            type: 'not_found_error',
            message: data.detail || 'Resource not found',
            status,
          });
        case 408:
          // Timeout
          return Promise.reject({
            type: 'timeout_error',
            message: data.detail || 'Request timed out',
            status,
          });
        case 413:
          // File too large
          return Promise.reject({
            type: 'file_too_large_error',
            message: data.detail || 'File size exceeds limit',
            status,
          });
        case 500:
        case 502:
        case 503:
          // Server errors
          return Promise.reject({
            type: 'server_error',
            message: data.detail || 'Server error occurred',
            status,
          });
        default:
          return Promise.reject({
            type: 'unknown_error',
            message: data.detail || 'An error occurred',
            status,
          });
      }
    } else if (error.request) {
      // Request made but no response received
      return Promise.reject({
        type: 'network_error',
        message: 'Network error. Please check your connection.',
        status: 0,
      });
    } else {
      // Error setting up request
      return Promise.reject({
        type: 'request_error',
        message: error.message || 'Failed to make request',
        status: 0,
      });
    }
  }
);

// Helper functions for common API operations
export const conversionAPI = {
  convertLaTeX: async (file, autoFix = false) => {
    const formData = new FormData();
    formData.append('file', file);

    return apiClient.post(`/convert?auto_fix=${autoFix}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  convertAudio: async (file, targetFormat = 'mp3', bitrate = '192k', sampleRate = null) => {
    const formData = new FormData();
    formData.append('file', file);

    const params = new URLSearchParams({
      target_format: targetFormat,
      bitrate: bitrate,
    });
    if (sampleRate) {
      params.append('sample_rate', sampleRate.toString());
    }

    return apiClient.post(`/convert-audio?${params.toString()}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  transcribeAudio: async (file, sourceConversionId = null, retain = false) => {
    const formData = new FormData();
    formData.append('file', file);

    const params = new URLSearchParams({ retain: retain.toString() });
    if (sourceConversionId) {
      params.append('source_conversion_id', sourceConversionId);
    }

    const query = params.toString();
    return apiClient.post(`/transcribe-audio${query ? `?${query}` : ''}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  convertImage: async (file, targetFormat = 'webp', quality = 'high', options = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    const params = new URLSearchParams({
      target_format: targetFormat,
      quality: String(quality),
      strip_metadata: String(options.stripMetadata ?? true),
    });
    if (options.maxWidth) params.append('max_width', String(options.maxWidth));
    if (options.maxHeight) params.append('max_height', String(options.maxHeight));
    return apiClient.post(`/convert-image?${params.toString()}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  convertText: async (file, targetFormat = 'html') => {
    const formData = new FormData();
    formData.append('file', file);
    const params = new URLSearchParams({ target_format: targetFormat });
    return apiClient.post(`/convert-text?${params.toString()}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  downloadPDF: async conversionId => {
    return apiClient.get(`/download/${conversionId}`, {
      responseType: 'blob',
    });
  },

  downloadAudio: async conversionId => {
    return apiClient.get(`/download-audio/${conversionId}`, {
      responseType: 'blob',
    });
  },

  downloadImage: async conversionId => {
    return apiClient.get(`/download-image/${conversionId}`, { responseType: 'blob' });
  },

  downloadText: async conversionId => {
    return apiClient.get(`/download-text/${conversionId}`, { responseType: 'blob' });
  },

  downloadGeneratedText: async conversionId => {
    return apiClient.get(`/download-generated-text/${conversionId}`, { responseType: 'blob' });
  },

  getTransformationHistory: async (limit = 50) => {
    return apiClient.get('/history/transformations', { params: { limit } });
  },

  getConversionStatus: async conversionId => {
    return apiClient.get(`/conversion/${conversionId}`);
  },

  getAudioConversionStatus: async conversionId => {
    return apiClient.get(`/audio-conversion/${conversionId}`);
  },
};

export default apiClient;
