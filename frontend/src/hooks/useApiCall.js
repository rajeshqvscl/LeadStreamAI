import { useState, useCallback } from 'react';

/**
 * Reusable hook for API calls with automatic error handling.
 * 
 * Usage:
 *   const { call, loading, error } = useApiCall();
 *   const data = await call(() => api.get('/api/leads/followups'));
 * 
 * Features:
 * - Automatic loading state management
 * - Error catching with user-friendly messages
 * - Abort controller support for cleanup
 * - Optional toast notifications
 */
export function useApiCall(options = {}) {
  const { 
    onError,        // callback(error) — custom error handler
    showToast = true, // show error notification
    errorMessage   // override default error message
  } = options;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const call = useCallback(async (apiFn, { signal } = {}) => {
    setLoading(true);
    setError(null);

    try {
      const result = await apiFn({ signal });
      return result;
    } catch (err) {
      // Don't show error for cancelled requests
      if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') {
        return null;
      }

      const msg = errorMessage 
        || err?.response?.data?.detail 
        || err?.response?.data?.error
        || err?.message 
        || 'Something went wrong';

      setError(msg);

      if (onError) {
        onError(err);
      } else if (showToast) {
        console.error('[API Error]', msg, err);
      }

      throw err;
    } finally {
      setLoading(false);
    }
  }, [errorMessage, onError, showToast]);

  const clearError = useCallback(() => setError(null), []);

  return { call, loading, error, clearError };
}

/**
 * Higher-order wrapper: wraps an async function with try/catch.
 * Returns [result, error, loading].
 * 
 * Usage:
 *   const [data, err, isLoading] = await safeCall(api.get('/api/leads'));
 */
export async function safeCall(promise) {
  try {
    const result = await promise;
    return [result, null, false];
  } catch (err) {
    if (err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED') {
      return [null, null, false];
    }
    return [null, err, false];
  }
}

/**
 * Extract user-friendly error message from axios error.
 */
export function getErrorMessage(err, fallback = 'Something went wrong') {
  if (!err) return fallback;
  return (
    err?.response?.data?.detail
    || err?.response?.data?.error
    || err?.message
    || fallback
  );
}
