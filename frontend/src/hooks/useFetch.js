import { useState, useEffect, useCallback, useRef } from 'react';
import api from '../services/api';

/**
 * Reusable data-fetching hook with loading, error, and auto-cleanup.
 *
 * Usage:
 *   const { data, loading, error, refetch } = useFetch('/api/leads', { params });
 *
 * Features:
 * - Automatic abort on unmount / param change
 * - Auto-retry on failure
 * - Safe state updates (no "state update on unmounted" warnings)
 */
export function useFetch(url, options = {}) {
  const {
    params,
    enabled = true,
    transform,      // (data) => transformedData
    fallbackData,   // initial data before first fetch
    onSuccess,      // callback(data)
    onError,        // callback(error)
    retryCount = 0, // auto-retry N times on failure
    dependencies = [],
  } = options;

  const [data, setData] = useState(fallbackData ?? null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async (retries = retryCount) => {
    if (!enabled || !url) {
      setLoading(false);
      return;
    }

    // Abort previous request
    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const res = await api.get(url, {
        params,
        signal: controller.signal,
      });

      if (!mountedRef.current) return;

      const result = transform ? transform(res.data) : res.data;
      setData(result);
      setError(null);

      if (onSuccess) onSuccess(result);
    } catch (err) {
      if (!mountedRef.current) return;

      // Don't show error for cancelled requests
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') {
        return;
      }

      // Auto-retry
      if (retries > 0) {
        setTimeout(() => fetchData(retries - 1), 1000);
        return;
      }

      const msg = err?.response?.data?.detail
        || err?.response?.data?.error
        || err?.message
        || 'Failed to load data';

      setError(msg);
      if (onError) onError(err);
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [url, JSON.stringify(params), enabled, ...dependencies]);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    return () => {
      mountedRef.current = false;
      if (abortRef.current) {
        abortRef.current.abort();
      }
    };
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

/**
 * Hook for POST/PUT/DELETE mutations with loading and error states.
 *
 * Usage:
 *   const { mutate, loading, error } = useMutation();
 *   await mutate(() => api.post('/api/leads', data));
 */
export function useMutation() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const mutate = useCallback(async (apiFn) => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiFn();
      return result;
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') {
        return null;
      }
      const msg = err?.response?.data?.detail
        || err?.response?.data?.error
        || err?.message
        || 'Operation failed';
      setError(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return { mutate, loading, error, clearError };
}
