import React, { useState, useEffect } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function App() {
  const [userId, setUserId] = useState('u_123');
  const [amount, setAmount] = useState('150.00');
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState(null);
  const [recentTask, setRecentTask] = useState(null);

  const [lookupUserId, setLookupUserId] = useState('u_123');
  const [userData, setUserData] = useState(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState(null);

  // Poll user data when a task is in progress
  useEffect(() => {
    let intervalId;
    if (recentTask && recentTask.status === 'processing') {
      intervalId = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/users/${recentTask.userId}`);
          if (res.ok) {
            const data = await res.json();
            setUserData(data);
            if (data.status === 'processed') {
              setRecentTask((prev) => ({ ...prev, status: 'processed' }));
              clearInterval(intervalId);
            }
          }
        } catch (err) {
          console.error('Polling error:', err);
        }
      }, 1000);
    }
    return () => clearInterval(intervalId);
  }, [recentTask]);

  const handleSubmitCredit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setNotification(null);

    const parsedAmount = parseFloat(amount);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setNotification({ type: 'error', message: 'Amount must be a positive number.' });
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/credits`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, amount: parsedAmount }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to submit credit');
      }

      const data = await response.json();
      setRecentTask({
        taskId: data.task_id,
        userId: userId,
        amount: parsedAmount,
        status: data.status,
      });

      setNotification({
        type: 'success',
        message: `Credit of $${parsedAmount.toFixed(2)} queued for ${userId}. Task ID: ${data.task_id}`,
      });

      // Also set the lookup id to match
      setLookupUserId(userId);
      fetchUserData(userId);
    } catch (err) {
      setNotification({ type: 'error', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  const fetchUserData = async (idToFetch) => {
    setLookupLoading(true);
    setLookupError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/users/${idToFetch}`);
      if (!response.ok) {
        if (response.status === 404) {
          setUserData(null);
          setLookupError(`User "${idToFetch}" does not exist yet.`);
        } else {
          throw new Error('Failed to fetch user data');
        }
        return;
      }
      const data = await response.json();
      setUserData(data);
    } catch (err) {
      setLookupError(err.message);
      setUserData(null);
    } finally {
      setLookupLoading(false);
    }
  };

  const handleLookup = (e) => {
    e.preventDefault();
    if (lookupUserId.trim()) {
      fetchUserData(lookupUserId.trim());
    }
  };

  return (
    <div style={{ maxWidth: 880, margin: '0 auto', padding: '2.5rem 1.5rem', width: '100%' }}>
      {/* Header */}
      <header style={{ marginBottom: '2.5rem', borderBottom: '1px solid #334155', paddingBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 700, color: '#38bdf8' }}>
              Async Credit Processing Service
            </h1>
            <p style={{ color: '#94a3b8', marginTop: '0.25rem' }}>
              FastAPI + Celery + Redis + MongoDB Architecture Console
            </p>
          </div>
          <span style={{
            fontSize: '0.75rem',
            padding: '0.25rem 0.75rem',
            borderRadius: 9999,
            backgroundColor: '#0369a1',
            color: '#e0f2fe',
            fontWeight: 600,
          }}>
            Dockerized Stack
          </span>
        </div>
      </header>

      {/* Main Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '2rem' }}>
        {/* Form Card */}
        <section style={{
          backgroundColor: '#1e293b',
          borderRadius: '0.75rem',
          padding: '1.5rem',
          border: '1px solid #334155',
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.2)',
        }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1.25rem', color: '#f1f5f9' }}>
            Add Credit to Account
          </h2>
          <form onSubmit={handleSubmitCredit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.875rem', color: '#cbd5e1', marginBottom: '0.375rem' }}>
                User ID
              </label>
              <input
                type="text"
                required
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="e.g. u_123"
                style={{
                  width: '100%',
                  padding: '0.625rem 0.75rem',
                  borderRadius: '0.375rem',
                  border: '1px solid #475569',
                  backgroundColor: '#0f172a',
                  color: '#fff',
                  fontSize: '0.95rem',
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.875rem', color: '#cbd5e1', marginBottom: '0.375rem' }}>
                Amount ($)
              </label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="e.g. 150.00"
                style={{
                  width: '100%',
                  padding: '0.625rem 0.75rem',
                  borderRadius: '0.375rem',
                  border: '1px solid #475569',
                  backgroundColor: '#0f172a',
                  color: '#fff',
                  fontSize: '0.95rem',
                }}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                marginTop: '0.5rem',
                backgroundColor: loading ? '#64748b' : '#0284c7',
                color: '#fff',
                padding: '0.75rem',
                borderRadius: '0.375rem',
                border: 'none',
                fontWeight: 600,
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'background-color 0.2s',
              }}
            >
              {loading ? 'Submitting to Queue...' : 'Apply Credit (POST /credits)'}
            </button>
          </form>

          {notification && (
            <div
              style={{
                marginTop: '1.25rem',
                padding: '0.75rem 1rem',
                borderRadius: '0.375rem',
                fontSize: '0.875rem',
                backgroundColor: notification.type === 'error' ? '#7f1d1d' : '#064e3b',
                color: notification.type === 'error' ? '#fecaca' : '#a7f3d0',
                border: `1px solid ${notification.type === 'error' ? '#991b1b' : '#047857'}`,
              }}
            >
              {notification.message}
            </div>
          )}
        </section>

        {/* User Status / Lookup Card */}
        <section style={{
          backgroundColor: '#1e293b',
          borderRadius: '0.75rem',
          padding: '1.5rem',
          border: '1px solid #334155',
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.2)',
          display: 'flex',
          flexDirection: 'column',
        }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1.25rem', color: '#f1f5f9' }}>
            Account Status & Live Balance
          </h2>

          <form onSubmit={handleLookup} style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem' }}>
            <input
              type="text"
              value={lookupUserId}
              onChange={(e) => setLookupUserId(e.target.value)}
              placeholder="Query User ID"
              style={{
                flex: 1,
                padding: '0.5rem 0.75rem',
                borderRadius: '0.375rem',
                border: '1px solid #475569',
                backgroundColor: '#0f172a',
                color: '#fff',
                fontSize: '0.9rem',
              }}
            />
            <button
              type="submit"
              disabled={lookupLoading}
              style={{
                backgroundColor: '#334155',
                color: '#f8fafc',
                padding: '0.5rem 1rem',
                borderRadius: '0.375rem',
                border: 'none',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Query
            </button>
          </form>

          {lookupError && (
            <div style={{ color: '#f87171', fontSize: '0.875rem', marginBottom: '1rem' }}>
              {lookupError}
            </div>
          )}

          {userData ? (
            <div style={{
              backgroundColor: '#0f172a',
              borderRadius: '0.5rem',
              padding: '1.25rem',
              border: '1px solid #334155',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                <span style={{ color: '#94a3b8', fontSize: '0.875rem' }}>User ID:</span>
                <span style={{ fontWeight: 600, color: '#f8fafc' }}>{userData.user_id}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                <span style={{ color: '#94a3b8', fontSize: '0.875rem' }}>Current Balance:</span>
                <span style={{ fontWeight: 700, fontSize: '1.2rem', color: '#34d399' }}>
                  ${Number(userData.balance).toFixed(2)}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#94a3b8', fontSize: '0.875rem' }}>Status:</span>
                <span style={{
                  padding: '0.2rem 0.6rem',
                  borderRadius: '0.25rem',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  backgroundColor: userData.status === 'processed' ? '#065f46' : '#854d0e',
                  color: userData.status === 'processed' ? '#34d399' : '#fde047',
                }}>
                  {userData.status}
                </span>
              </div>
            </div>
          ) : (
            <div style={{ color: '#64748b', fontSize: '0.875rem', textAlign: 'center', margin: 'auto 0' }}>
              No user record currently loaded. Submit a credit or query a user ID above.
            </div>
          )}

          {recentTask && (
            <div style={{ marginTop: '1.25rem', borderTop: '1px solid #334155', paddingTop: '1rem' }}>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
                Recent Task ID:
              </div>
              <code style={{ fontSize: '0.75rem', color: '#38bdf8', wordBreak: 'break-all' }}>
                {recentTask.taskId}
              </code>
            </div>
          )}
        </section>
      </div>

      {/* Footer Info */}
      <footer style={{ marginTop: '3rem', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>
        Designed for Basta Tech Lead Take-Home Exercise • Fully containerized architecture
      </footer>
    </div>
  );
}
