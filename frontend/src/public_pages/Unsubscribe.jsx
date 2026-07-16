import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

export default function Unsubscribe() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token) {
      setError('Missing unsubscribe token.');
      setLoading(false);
      return;
    }
    fetch(`/api/public/unsubscribe/validate?token=${encodeURIComponent(token)}`)
      .then((r) => {
        if (!r.ok) return r.json().then((e) => { throw new Error(e.detail || 'Invalid link'); });
        return r.json();
      })
      .then((json) => {
        setData(json);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [token]);

  const handleUnsubscribe = async () => {
    setSubmitting(true);
    try {
      const res = await fetch('/api/public/unsubscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Unsubscribe failed');
      }
      navigate('/unsubscribe/success?action=unsubscribed');
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  };

  const handleKeep = () => {
    navigate('/unsubscribe/success?action=kept');
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: '#0b0f19', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'sans-serif' }}>
        <div style={{ textAlign: 'center', color: '#94a3b8' }}>
          <div style={{ width: 40, height: 40, border: '4px solid #6366f1', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 16px' }}></div>
          <p>Loading your preferences...</p>
          <style>{'@keyframes spin { to { transform: rotate(360deg) } }'}</style>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ minHeight: '100vh', background: '#0b0f19', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'sans-serif' }}>
        <div style={{ maxWidth: 440, width: '90%', background: '#1e293b', borderRadius: 16, padding: 40, textAlign: 'center', border: '1px solid #334155' }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>🔗</div>
          <h1 style={{ color: '#f87171', fontSize: 22, margin: '0 0 8px' }}>Invalid Link</h1>
          <p style={{ color: '#94a3b8', fontSize: 14, lineHeight: 1.6 }}>{error}</p>
        </div>
      </div>
    );
  }

  const alreadyUnsubscribed = data?.is_unsubscribed;

  return (
    <div style={{ minHeight: '100vh', background: '#0b0f19', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'sans-serif' }}>
      <div style={{ maxWidth: 480, width: '90%', background: '#1e293b', borderRadius: 16, padding: 40, border: '1px solid #334155' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <h1 style={{ color: '#f1f5f9', fontSize: 24, margin: '0 0 4px' }}>LeadStream</h1>
          <p style={{ color: '#64748b', fontSize: 14, margin: 0 }}>Email Preferences</p>
        </div>

        <div style={{ background: '#0f172a', borderRadius: 12, padding: 20, marginBottom: 24 }}>
          <p style={{ color: '#e2e8f0', fontSize: 15, margin: '0 0 4px' }}>{data?.email}</p>
          {data?.company && (
            <p style={{ color: '#64748b', fontSize: 13, margin: 0 }}>{data.company}</p>
          )}
          <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: alreadyUnsubscribed ? '#f87171' : '#34d399' }}></div>
            <span style={{ color: alreadyUnsubscribed ? '#f87171' : '#34d399', fontSize: 13, fontWeight: 600 }}>
              {alreadyUnsubscribed ? 'Unsubscribed' : 'Subscribed'}
            </span>
          </div>
        </div>

        {alreadyUnsubscribed ? (
          <div style={{ textAlign: 'center' }}>
            <p style={{ color: '#94a3b8', fontSize: 14, lineHeight: 1.6, marginBottom: 20 }}>
              You have already been removed from our outreach list.
            </p>
            <button
              onClick={() => navigate('/unsubscribe/resubscribe?token=' + encodeURIComponent(token))}
              style={{ background: '#6366f1', color: '#fff', border: 'none', padding: '12px 32px', borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
            >
              Resubscribe
            </button>
          </div>
        ) : (
          <>
            <p style={{ color: '#94a3b8', fontSize: 14, lineHeight: 1.6, textAlign: 'center', marginBottom: 24 }}>
              Do you want to stop receiving automated outreach emails?
            </p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button
                onClick={handleKeep}
                style={{ background: '#334155', color: '#e2e8f0', border: '1px solid #475569', padding: '12px 24px', borderRadius: 10, fontSize: 14, fontWeight: 500, cursor: 'pointer' }}
              >
                Keep Me Subscribed
              </button>
              <button
                onClick={handleUnsubscribe}
                disabled={submitting}
                style={{ background: '#ef4444', color: '#fff', border: 'none', padding: '12px 24px', borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: submitting ? 'not-allowed' : 'pointer', opacity: submitting ? 0.6 : 1 }}
              >
                {submitting ? 'Processing...' : 'Unsubscribe'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
