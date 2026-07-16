import React, { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') || '';

export default function Resubscribe() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');

  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState(null);

  const handleResubscribe = async () => {
    if (!token) {
      setError('Missing token.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/public/resubscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Resubscribe failed');
      }
      setDone(true);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div style={{ minHeight: '100vh', background: '#0b0f19', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'sans-serif' }}>
        <div style={{ maxWidth: 440, width: '90%', background: '#1e293b', borderRadius: 16, padding: 40, textAlign: 'center', border: '1px solid #334155' }}>
          <div style={{ fontSize: 56, marginBottom: 16 }}>✅</div>
          <h1 style={{ color: '#34d399', fontSize: 22, margin: '0 0 8px' }}>Successfully Resubscribed</h1>
          <p style={{ color: '#94a3b8', fontSize: 14, lineHeight: 1.6, marginBottom: 24 }}>
            You're back on our outreach list. You will receive future emails.
          </p>
          <button
            onClick={() => window.close()}
            style={{ background: '#334155', color: '#e2e8f0', border: '1px solid #475569', padding: '12px 32px', borderRadius: 10, fontSize: 14, fontWeight: 500, cursor: 'pointer' }}
          >
            Close This Window
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0b0f19', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'sans-serif' }}>
      <div style={{ maxWidth: 440, width: '90%', background: '#1e293b', borderRadius: 16, padding: 40, textAlign: 'center', border: '1px solid #334155' }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>🔄</div>
        <h1 style={{ color: '#f1f5f9', fontSize: 22, margin: '0 0 8px' }}>Resubscribe</h1>
        <p style={{ color: '#94a3b8', fontSize: 14, lineHeight: 1.6, marginBottom: 24 }}>
          Would you like to start receiving outreach emails again?
        </p>

        {error && (
          <p style={{ color: '#f87171', fontSize: 13, marginBottom: 16 }}>{error}</p>
        )}

        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <button
            onClick={() => window.close()}
            style={{ background: '#334155', color: '#e2e8f0', border: '1px solid #475569', padding: '12px 24px', borderRadius: 10, fontSize: 14, fontWeight: 500, cursor: 'pointer' }}
          >
            Cancel
          </button>
          <button
            onClick={handleResubscribe}
            disabled={submitting}
            style={{ background: '#6366f1', color: '#fff', border: 'none', padding: '12px 24px', borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: submitting ? 'not-allowed' : 'pointer', opacity: submitting ? 0.6 : 1 }}
          >
            {submitting ? 'Processing...' : 'Yes, Resubscribe'}
          </button>
        </div>
      </div>
    </div>
  );
}
