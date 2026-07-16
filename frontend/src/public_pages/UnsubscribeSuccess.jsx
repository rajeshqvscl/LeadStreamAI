import React from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

export default function UnsubscribeSuccess() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const action = searchParams.get('action');

  const isUnsubscribed = action === 'unsubscribed';
  const isKept = action === 'kept';

  return (
    <div style={{ minHeight: '100vh', background: '#0b0f19', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'sans-serif' }}>
      <div style={{ maxWidth: 440, width: '90%', background: '#1e293b', borderRadius: 16, padding: 40, textAlign: 'center', border: '1px solid #334155' }}>
        <div style={{ fontSize: 56, marginBottom: 16 }}>
          {isUnsubscribed ? '🎉' : '👍'}
        </div>

        {isUnsubscribed && (
          <>
            <h1 style={{ color: '#34d399', fontSize: 22, margin: '0 0 8px' }}>Successfully Unsubscribed</h1>
            <p style={{ color: '#94a3b8', fontSize: 14, lineHeight: 1.6, marginBottom: 8 }}>
              We've removed you from future outreach emails.
            </p>
            <p style={{ color: '#64748b', fontSize: 13, lineHeight: 1.6, marginBottom: 24 }}>
              You may still receive transactional emails related to your account.
            </p>
          </>
        )}

        {isKept && (
          <>
            <h1 style={{ color: '#6366f1', fontSize: 22, margin: '0 0 8px' }}>You're Still Subscribed</h1>
            <p style={{ color: '#94a3b8', fontSize: 14, lineHeight: 1.6, marginBottom: 24 }}>
              You have not been unsubscribed. You will continue to receive our emails.
            </p>
          </>
        )}

        {!isUnsubscribed && !isKept && (
          <>
            <h1 style={{ color: '#f1f5f9', fontSize: 22, margin: '0 0 8px' }}>Preferences Updated</h1>
            <p style={{ color: '#94a3b8', fontSize: 14, lineHeight: 1.6, marginBottom: 24 }}>
              Your email preferences have been updated.
            </p>
          </>
        )}

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
