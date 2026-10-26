import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Users,
  User,
  CreditCard,
  Clock,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  RefreshCw,
  Plus,
  DollarSign,
  Activity,
  ArrowRight,
  Filter,
  Check,
  Copy,
  Zap,
  ShieldAlert
} from 'lucide-react';

// Connect either directly to FastAPI on localhost:8000 or via reverse proxy (/api)
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== 'undefined' && window.location.port === '3000' && window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : '/api');

export default function App() {
  // User directory state
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [selectedUserId, setSelectedUserId] = useState('u_123');
  const [searchQuery, setSearchQuery] = useState('');

  // Credit submission form state
  const [formUserId, setFormUserId] = useState('u_123');
  const [amount, setAmount] = useState('150.00');
  const [submitting, setSubmitting] = useState(false);
  const [notification, setNotification] = useState(null);

  // New user input inline form
  const [isAddingNewUser, setIsAddingNewUser] = useState(false);
  const [newUserIdInput, setNewUserIdInput] = useState('');

  // Tracked credit tasks (queue of processing, processed, and failed_duplicate items)
  const [tasks, setTasks] = useState([]);
  const [sideFilter, setSideFilter] = useState('all'); // 'all' | 'selected'
  const [taskCategoryFilter, setTaskCategoryFilter] = useState('all'); // 'all' | 'processed' | 'duplicates'
  const [copiedTaskId, setCopiedTaskId] = useState(null);

  // Fetch all users from API
  const fetchUsers = useCallback(async () => {
    setUsersLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/users`);
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
        if (data.length > 0 && !selectedUserId) {
          setSelectedUserId(data[0].user_id);
          setFormUserId(data[0].user_id);
        }
      }
    } catch (err) {
      console.error('Failed to load users:', err);
    } finally {
      setUsersLoading(false);
    }
  }, [selectedUserId]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // Fetch fresh balance for a specific user directly from MongoDB
  const fetchFreshUserBalance = useCallback(async (uId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/users/${uId}`);
      if (res.ok) {
        const freshUser = await res.json();
        setUsers((prev) =>
          prev.map((u) =>
            u.user_id === uId
              ? { ...u, balance: freshUser.balance, status: freshUser.status }
              : u
          )
        );
        return freshUser;
      }
    } catch (err) {
      console.error(`Failed to fetch fresh balance for ${uId}:`, err);
    }
    return null;
  }, []);

  // Synchronize form user ID when selecting a user from the directory
  const handleSelectUser = (uId) => {
    setSelectedUserId(uId);
    setFormUserId(uId);
  };

  // Live polling loop for active in-flight tasks
  useEffect(() => {
    const activeTasks = tasks.filter((t) => t.status === 'processing');
    if (activeTasks.length === 0) return;

    const intervalId = setInterval(async () => {
      let anyStatusChanged = false;

      for (const task of activeTasks) {
        try {
          // Poll Celery & MongoDB task status
          const res = await fetch(`${API_BASE_URL}/credits/${task.taskId}`);
          if (!res.ok) continue;

          const taskData = await res.json();
          const taskStatus = taskData.task_status || taskData.result?.status;
          const isFinished =
            taskData.status === 'SUCCESS' ||
            taskStatus === 'processed' ||
            taskStatus === 'failed_duplicate' ||
            taskStatus === 'revoked_duplicate';

          if (isFinished) {
            anyStatusChanged = true;

            // CASE 1: Event failed due to duplicate submission within 5 minutes
            if (taskStatus === 'failed_duplicate' || taskStatus === 'revoked_duplicate') {
              const reason =
                taskData.error_message ||
                taskData.result?.error ||
                `Duplicate credit of $${task.amount} detected within the 5-minute deduplication window.`;

              setTasks((prev) =>
                prev.map((t) =>
                  t.taskId === task.taskId
                    ? {
                        ...t,
                        status: 'failed_duplicate',
                        errorMessage: reason,
                        completedAt: new Date(),
                      }
                    : t
                )
              );

              // Verify user balance remains unchanged
              await fetchFreshUserBalance(task.userId);

              setNotification({
                type: 'warning',
                message: `Duplicate rejected for ${task.userId}: Credit of $${Number(task.amount).toFixed(2)} was not applied.`,
              });
            }
            // CASE 2: Event successfully processed
            else {
              // 1. Immediately fetch the fresh overall balance from MongoDB
              const freshUser = await fetchFreshUserBalance(task.userId);

              setTasks((prev) =>
                prev.map((t) =>
                  t.taskId === task.taskId
                    ? {
                        ...t,
                        status: 'processed',
                        completedAt: new Date(),
                        finalBalance: freshUser ? freshUser.balance : undefined,
                      }
                    : t
                )
              );

              setNotification({
                type: 'success',
                message: `Credit of $${Number(task.amount).toFixed(2)} processed! ${task.userId}'s new balance: $${Number(freshUser?.balance || 0).toFixed(2)}.`,
              });
            }
          }
        } catch (err) {
          console.error('Error polling task:', task.taskId, err);
        }
      }

      if (anyStatusChanged) {
        // Refresh entire directory so all balances and statuses are 100% current
        fetchUsers();
      }
    }, 1200);

    return () => clearInterval(intervalId);
  }, [tasks, fetchFreshUserBalance, fetchUsers]);

  // Handle Add Credit Form Submission
  const handleSubmitCredit = async (e) => {
    e.preventDefault();
    const cleanUserId = formUserId.trim();
    const parsedAmount = parseFloat(amount);

    if (!cleanUserId) {
      setNotification({ type: 'error', message: 'User ID cannot be empty.' });
      return;
    }

    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setNotification({ type: 'error', message: 'Amount must be greater than $0.00.' });
      return;
    }

    setSubmitting(true);
    setNotification(null);

    try {
      const response = await fetch(`${API_BASE_URL}/credits`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: cleanUserId, amount: parsedAmount }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to submit credit request');
      }

      const data = await response.json();

      const newTask = {
        taskId: data.task_id,
        userId: cleanUserId,
        amount: parsedAmount,
        status: 'processing',
        createdAt: new Date(),
      };

      setTasks((prev) => [newTask, ...prev]);

      // Set user status to processing in directory
      setUsers((prev) => {
        const exists = prev.some((u) => u.user_id === cleanUserId);
        if (exists) {
          return prev.map((u) => (u.user_id === cleanUserId ? { ...u, status: 'processing' } : u));
        } else {
          return [{ user_id: cleanUserId, balance: 0.0, status: 'processing' }, ...prev];
        }
      });

      setSelectedUserId(cleanUserId);
      setNotification({
        type: 'info',
        message: `Credit request enqueued for ${cleanUserId} ($${parsedAmount.toFixed(2)}). Checking deduplication window...`,
      });
    } catch (err) {
      setNotification({ type: 'error', message: err.message });
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddNewUser = (e) => {
    e.preventDefault();
    if (!newUserIdInput.trim()) return;
    const cleanId = newUserIdInput.trim();
    if (!users.some((u) => u.user_id === cleanId)) {
      setUsers((prev) => [{ user_id: cleanId, balance: 0.0, status: 'new' }, ...prev]);
    }
    setSelectedUserId(cleanId);
    setFormUserId(cleanId);
    setNewUserIdInput('');
    setIsAddingNewUser(false);
  };

  const handleCopyTaskId = (id) => {
    navigator.clipboard.writeText(id);
    setCopiedTaskId(id);
    setTimeout(() => setCopiedTaskId(null), 2000);
  };

  // Filtered users for search
  const filteredUsers = useMemo(() => {
    if (!searchQuery.trim()) return users;
    return users.filter((u) => u.user_id.toLowerCase().includes(searchQuery.toLowerCase()));
  }, [users, searchQuery]);

  // Selected user info
  const selectedUser = useMemo(() => {
    return users.find((u) => u.user_id === selectedUserId);
  }, [users, selectedUserId]);

  // Filter tasks based on selected user and category
  const displayedTasks = useMemo(() => {
    let list = tasks;
    if (sideFilter === 'selected' && selectedUserId) {
      list = list.filter((t) => t.userId === selectedUserId);
    }
    if (taskCategoryFilter === 'processed') {
      list = list.filter((t) => t.status === 'processed');
    } else if (taskCategoryFilter === 'duplicates') {
      list = list.filter((t) => t.status === 'failed_duplicate' || t.status === 'revoked_duplicate');
    }
    return list;
  }, [tasks, sideFilter, selectedUserId, taskCategoryFilter]);

  const activeTasks = displayedTasks.filter((t) => t.status === 'processing');
  const duplicateTasks = displayedTasks.filter(
    (t) => t.status === 'failed_duplicate' || t.status === 'revoked_duplicate'
  );
  const processedTasks = displayedTasks.filter((t) => t.status === 'processed');

  const globalActiveCount = tasks.filter((t) => t.status === 'processing').length;
  const globalDuplicateCount = tasks.filter(
    (t) => t.status === 'failed_duplicate' || t.status === 'revoked_duplicate'
  ).length;
  const globalProcessedCount = tasks.filter((t) => t.status === 'processed').length;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#0b0f19' }}>
      {/* Top Navigation / App Header */}
      <header
        style={{
          backgroundColor: '#111827',
          borderBottom: '1px solid #1f2937',
          padding: '1rem 2rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div
            style={{
              width: 38,
              height: 38,
              borderRadius: '0.5rem',
              backgroundColor: '#0284c7',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
            }}
          >
            <Zap size={22} />
          </div>
          <div>
            <h1 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f9fafb', letterSpacing: '-0.02em' }}>
              Async Credit Processing Engine
            </h1>
            <p style={{ fontSize: '0.8rem', color: '#9ca3af', marginTop: '0.1rem' }}>
              FastAPI • Celery • Deduplication Guard • MongoDB
            </p>
          </div>
        </div>

        {/* Global Live Counters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          {/* Active Processing Pill */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              backgroundColor: '#1e293b',
              padding: '0.4rem 0.85rem',
              borderRadius: '9999px',
              border: '1px solid #334155',
              fontSize: '0.8rem',
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                backgroundColor: globalActiveCount > 0 ? '#f59e0b' : '#10b981',
                boxShadow: globalActiveCount > 0 ? '0 0 8px #f59e0b' : '0 0 8px #10b981',
              }}
              className={globalActiveCount > 0 ? 'animate-pulse-slow' : ''}
            />
            <span style={{ color: '#cbd5e1' }}>
              {globalActiveCount > 0 ? `${globalActiveCount} Processing` : 'Workers Idle'}
            </span>
          </div>

          {/* Duplicates Blocked Counter Pill */}
          {globalDuplicateCount > 0 && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                backgroundColor: '#3b1812',
                padding: '0.4rem 0.85rem',
                borderRadius: '9999px',
                border: '1px solid #7c2d12',
                fontSize: '0.8rem',
                color: '#fdba74',
              }}
            >
              <ShieldAlert size={14} color="#f97316" />
              <span>{globalDuplicateCount} Duplicates Blocked</span>
            </div>
          )}

          <button
            onClick={fetchUsers}
            disabled={usersLoading}
            title="Refresh Users and Balances"
            style={{
              backgroundColor: '#1f2937',
              border: '1px solid #374151',
              color: '#9ca3af',
              borderRadius: '0.375rem',
              padding: '0.45rem 0.75rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontSize: '0.8rem',
              cursor: usersLoading ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
            }}
          >
            <RefreshCw size={14} className={usersLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </header>

      {/* Main Content Layout (2 Columns: Main Experience + Processing Side Panel) */}
      <main
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.25fr) minmax(420px, 1fr)',
          maxWidth: 1440,
          width: '100%',
          margin: '0 auto',
          padding: '1.75rem 2rem',
          gap: '2rem',
        }}
      >
        {/* LEFT COLUMN: User Directory & Add Credit Form */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
          {/* USER DIRECTORY CARD */}
          <div
            style={{
              backgroundColor: '#111827',
              borderRadius: '0.875rem',
              border: '1px solid #1f2937',
              padding: '1.5rem',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.25)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '1.25rem',
                flexWrap: 'wrap',
                gap: '0.75rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Users size={19} color="#38bdf8" />
                <h2 style={{ fontSize: '1.15rem', fontWeight: 600, color: '#f3f4f6' }}>
                  Accounts Directory
                </h2>
                <span
                  style={{
                    backgroundColor: '#1f2937',
                    color: '#9ca3af',
                    fontSize: '0.75rem',
                    padding: '0.15rem 0.5rem',
                    borderRadius: '9999px',
                    fontWeight: 600,
                  }}
                >
                  {users.length}
                </span>
              </div>

              {/* Add New User Toggle */}
              <button
                onClick={() => setIsAddingNewUser(!isAddingNewUser)}
                style={{
                  backgroundColor: '#1e293b',
                  color: '#38bdf8',
                  border: '1px solid #0284c7',
                  padding: '0.35rem 0.75rem',
                  borderRadius: '0.375rem',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  cursor: 'pointer',
                }}
              >
                <Plus size={14} />
                New User
              </button>
            </div>

            {/* Inline New User Creator */}
            {isAddingNewUser && (
              <form
                onSubmit={handleAddNewUser}
                style={{
                  display: 'flex',
                  gap: '0.5rem',
                  marginBottom: '1rem',
                  backgroundColor: '#1e293b',
                  padding: '0.75rem',
                  borderRadius: '0.5rem',
                  border: '1px dashed #0284c7',
                }}
              >
                <input
                  type="text"
                  placeholder="e.g. u_999 or user_bob"
                  value={newUserIdInput}
                  onChange={(e) => setNewUserIdInput(e.target.value)}
                  style={{
                    flex: 1,
                    backgroundColor: '#0b0f19',
                    border: '1px solid #374151',
                    borderRadius: '0.375rem',
                    padding: '0.4rem 0.75rem',
                    color: '#f9fafb',
                    fontSize: '0.85rem',
                  }}
                  autoFocus
                />
                <button
                  type="submit"
                  style={{
                    backgroundColor: '#0284c7',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '0.375rem',
                    padding: '0.4rem 0.9rem',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Add & Select
                </button>
                <button
                  type="button"
                  onClick={() => setIsAddingNewUser(false)}
                  style={{
                    backgroundColor: 'transparent',
                    color: '#9ca3af',
                    border: '1px solid #374151',
                    borderRadius: '0.375rem',
                    padding: '0.4rem 0.6rem',
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
              </form>
            )}

            {/* Search filter */}
            <div style={{ position: 'relative', marginBottom: '1rem' }}>
              <input
                type="text"
                placeholder="Search accounts by User ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  backgroundColor: '#0b0f19',
                  border: '1px solid #1f2937',
                  borderRadius: '0.5rem',
                  padding: '0.55rem 0.85rem',
                  color: '#e5e7eb',
                  fontSize: '0.85rem',
                }}
              />
            </div>

            {/* User Cards Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                gap: '0.75rem',
                maxHeight: 250,
                overflowY: 'auto',
                paddingRight: '0.25rem',
              }}
            >
              {filteredUsers.length === 0 ? (
                <div style={{ color: '#6b7280', fontSize: '0.85rem', gridColumn: '1 / -1', padding: '1rem 0' }}>
                  No users found. Click &quot;New User&quot; or enter one below.
                </div>
              ) : (
                filteredUsers.map((u) => {
                  const isSelected = u.user_id === selectedUserId;
                  const isProcessing =
                    u.status === 'processing' ||
                    tasks.some((t) => t.userId === u.user_id && t.status === 'processing');

                  return (
                    <div
                      key={u.user_id}
                      onClick={() => handleSelectUser(u.user_id)}
                      style={{
                        backgroundColor: isSelected ? '#1e293b' : '#0f172a',
                        border: isSelected ? '1.5px solid #0284c7' : '1px solid #1e293b',
                        borderRadius: '0.625rem',
                        padding: '0.85rem',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease-in-out',
                        position: 'relative',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f3f4f6' }}>
                          {u.user_id}
                        </span>
                        <span
                          style={{
                            fontSize: '0.7rem',
                            fontWeight: 600,
                            padding: '0.15rem 0.45rem',
                            borderRadius: '9999px',
                            backgroundColor: isProcessing ? '#78350f' : '#064e3b',
                            color: isProcessing ? '#fde047' : '#34d399',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                          }}
                        >
                          {isProcessing && (
                            <span
                              style={{ width: 5, height: 5, borderRadius: '50%', backgroundColor: '#fde047' }}
                              className="animate-pulse-slow"
                            />
                          )}
                          {isProcessing ? 'processing' : u.status}
                        </span>
                      </div>

                      <div style={{ marginTop: '0.65rem' }}>
                        <span style={{ fontSize: '0.7rem', color: '#9ca3af', display: 'block' }}>
                          Live Balance
                        </span>
                        <span style={{ fontSize: '1.2rem', fontWeight: 700, color: '#38bdf8' }}>
                          ${Number(u.balance || 0).toFixed(2)}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* ADD CREDIT FORM CARD */}
          <div
            style={{
              backgroundColor: '#111827',
              borderRadius: '0.875rem',
              border: '1px solid #1f2937',
              padding: '1.5rem',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.25)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <CreditCard size={19} color="#38bdf8" />
                <h2 style={{ fontSize: '1.15rem', fontWeight: 600, color: '#f3f4f6' }}>
                  Add Credit to User
                </h2>
              </div>
              {selectedUser && (
                <div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
                  Current Balance: <strong style={{ color: '#38bdf8' }}>${Number(selectedUser.balance || 0).toFixed(2)}</strong>
                </div>
              )}
            </div>

            <form onSubmit={handleSubmitCredit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* User ID Field */}
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#9ca3af', marginBottom: '0.4rem', fontWeight: 500 }}>
                  Target User Account
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type="text"
                    required
                    value={formUserId}
                    onChange={(e) => {
                      setFormUserId(e.target.value);
                      setSelectedUserId(e.target.value);
                    }}
                    placeholder="e.g. u_123"
                    style={{
                      width: '100%',
                      backgroundColor: '#0b0f19',
                      border: '1px solid #374151',
                      borderRadius: '0.5rem',
                      padding: '0.65rem 0.85rem 0.65rem 2.25rem',
                      color: '#ffffff',
                      fontSize: '0.95rem',
                    }}
                  />
                  <User
                    size={16}
                    color="#6b7280"
                    style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)' }}
                  />
                </div>
              </div>

              {/* Amount Field & Quick Presets */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                  <label style={{ fontSize: '0.85rem', color: '#9ca3af', fontWeight: 500 }}>
                    Credit Amount ($)
                  </label>
                  <span style={{ fontSize: '0.75rem', color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <ShieldAlert size={12} />
                    5-min deduplication guard active
                  </span>
                </div>
                <div style={{ position: 'relative' }}>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="0.00"
                    style={{
                      width: '100%',
                      backgroundColor: '#0b0f19',
                      border: '1px solid #374151',
                      borderRadius: '0.5rem',
                      padding: '0.65rem 0.85rem 0.65rem 2.25rem',
                      color: '#ffffff',
                      fontSize: '1rem',
                      fontWeight: 600,
                    }}
                  />
                  <DollarSign
                    size={16}
                    color="#6b7280"
                    style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)' }}
                  />
                </div>

                {/* Quick Add Presets */}
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.6rem', flexWrap: 'wrap' }}>
                  {['25.00', '50.00', '88.00', '100.00', '150.00'].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setAmount(preset)}
                      style={{
                        backgroundColor: amount === preset ? '#0284c7' : '#1e293b',
                        color: amount === preset ? '#ffffff' : '#cbd5e1',
                        border: '1px solid #334155',
                        borderRadius: '0.375rem',
                        padding: '0.3rem 0.65rem',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      +${parseFloat(preset).toFixed(0)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Submit CTA */}
              <button
                type="submit"
                disabled={submitting}
                style={{
                  backgroundColor: submitting ? '#0369a1' : '#0284c7',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '0.5rem',
                  padding: '0.85rem',
                  fontSize: '0.95rem',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                  cursor: submitting ? 'not-allowed' : 'pointer',
                  boxShadow: '0 4px 10px rgba(2, 132, 199, 0.3)',
                  transition: 'background-color 0.15s',
                }}
              >
                {submitting ? (
                  <>
                    <RefreshCw size={18} className="animate-spin" />
                    Enqueuing to Celery Task Queue...
                  </>
                ) : (
                  <>
                    Apply Credit (POST /credits)
                    <ArrowRight size={17} />
                  </>
                )}
              </button>
            </form>

            {/* Notification alert */}
            {notification && (
              <div
                className="animate-slide-in"
                style={{
                  marginTop: '1.25rem',
                  padding: '0.75rem 1rem',
                  borderRadius: '0.5rem',
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.6rem',
                  backgroundColor:
                    notification.type === 'error'
                      ? '#450a0a'
                      : notification.type === 'warning'
                      ? '#451a03'
                      : notification.type === 'info'
                      ? '#082f49'
                      : '#064e3b',
                  color:
                    notification.type === 'error'
                      ? '#fca5a5'
                      : notification.type === 'warning'
                      ? '#fcd34d'
                      : notification.type === 'info'
                      ? '#7dd3fc'
                      : '#a7f3d0',
                  border: `1px solid ${
                    notification.type === 'error'
                      ? '#7f1d1d'
                      : notification.type === 'warning'
                      ? '#92400e'
                      : notification.type === 'info'
                      ? '#0284c7'
                      : '#047857'
                  }`,
                }}
              >
                {notification.type === 'error' ? (
                  <AlertCircle size={18} />
                ) : notification.type === 'warning' ? (
                  <ShieldAlert size={18} />
                ) : notification.type === 'info' ? (
                  <Activity size={18} className="animate-pulse-slow" />
                ) : (
                  <CheckCircle2 size={18} />
                )}
                <span>{notification.message}</span>
              </div>
            )}
          </div>
        </section>

        {/* RIGHT COLUMN ("ON THE SIDE"): REAL-TIME PROCESSING MONITOR */}
        <aside
          style={{
            backgroundColor: '#111827',
            borderRadius: '0.875rem',
            border: '1px solid #1f2937',
            padding: '1.5rem',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.25)',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Header of Side Panel */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '1rem',
              paddingBottom: '0.75rem',
              borderBottom: '1px solid #1f2937',
              flexWrap: 'wrap',
              gap: '0.5rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Activity size={19} color="#38bdf8" />
              <div>
                <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f3f4f6' }}>
                  Processing Monitor
                </h2>
                <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>
                  Real-time Task & Deduplication Stream
                </span>
              </div>
            </div>

            {/* Filter Toggle: All vs Selected User */}
            <div style={{ display: 'flex', backgroundColor: '#0b0f19', padding: '0.2rem', borderRadius: '0.375rem', border: '1px solid #1f2937' }}>
              <button
                onClick={() => setSideFilter('all')}
                style={{
                  backgroundColor: sideFilter === 'all' ? '#1f2937' : 'transparent',
                  color: sideFilter === 'all' ? '#ffffff' : '#9ca3af',
                  border: 'none',
                  borderRadius: '0.25rem',
                  padding: '0.25rem 0.55rem',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                All
              </button>
              <button
                onClick={() => setSideFilter('selected')}
                style={{
                  backgroundColor: sideFilter === 'selected' ? '#1f2937' : 'transparent',
                  color: sideFilter === 'selected' ? '#ffffff' : '#9ca3af',
                  border: 'none',
                  borderRadius: '0.25rem',
                  padding: '0.25rem 0.55rem',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                User ({selectedUserId || 'none'})
              </button>
            </div>
          </div>

          {/* Category Tabs: All, Processed, Duplicates */}
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
            <button
              onClick={() => setTaskCategoryFilter('all')}
              style={{
                flex: 1,
                padding: '0.35rem 0.5rem',
                fontSize: '0.75rem',
                fontWeight: 600,
                borderRadius: '0.375rem',
                border: '1px solid',
                borderColor: taskCategoryFilter === 'all' ? '#0284c7' : '#1f2937',
                backgroundColor: taskCategoryFilter === 'all' ? '#082f49' : '#0b0f19',
                color: taskCategoryFilter === 'all' ? '#38bdf8' : '#9ca3af',
                cursor: 'pointer',
              }}
            >
              All Events ({displayedTasks.length})
            </button>
            <button
              onClick={() => setTaskCategoryFilter('processed')}
              style={{
                flex: 1,
                padding: '0.35rem 0.5rem',
                fontSize: '0.75rem',
                fontWeight: 600,
                borderRadius: '0.375rem',
                border: '1px solid',
                borderColor: taskCategoryFilter === 'processed' ? '#059669' : '#1f2937',
                backgroundColor: taskCategoryFilter === 'processed' ? '#064e3b' : '#0b0f19',
                color: taskCategoryFilter === 'processed' ? '#34d399' : '#9ca3af',
                cursor: 'pointer',
              }}
            >
              Processed ({processedTasks.length})
            </button>
            <button
              onClick={() => setTaskCategoryFilter('duplicates')}
              style={{
                flex: 1,
                padding: '0.35rem 0.5rem',
                fontSize: '0.75rem',
                fontWeight: 600,
                borderRadius: '0.375rem',
                border: '1px solid',
                borderColor: taskCategoryFilter === 'duplicates' ? '#dc2626' : '#1f2937',
                backgroundColor: taskCategoryFilter === 'duplicates' ? '#450a0a' : '#0b0f19',
                color: taskCategoryFilter === 'duplicates' ? '#f87171' : '#9ca3af',
                cursor: 'pointer',
              }}
            >
              Duplicates ({duplicateTasks.length})
            </button>
          </div>

          {/* SECTION 1: Active In-Flight Processing Tasks */}
          {(taskCategoryFilter === 'all' || taskCategoryFilter === 'processed') && (
            <div style={{ marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#f59e0b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Active in Queue ({activeTasks.length})
                </span>
                {activeTasks.length > 0 && (
                  <span style={{ fontSize: '0.7rem', color: '#fde047', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <RefreshCw size={11} className="animate-spin" />
                    Polling Worker...
                  </span>
                )}
              </div>

              {activeTasks.length === 0 ? (
                <div
                  style={{
                    backgroundColor: '#0b0f19',
                    border: '1px dashed #1f2937',
                    borderRadius: '0.5rem',
                    padding: '0.85rem',
                    textAlign: 'center',
                    color: '#6b7280',
                    fontSize: '0.8rem',
                  }}
                >
                  No credits currently in flight.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  {activeTasks.map((task) => (
                    <div
                      key={task.taskId}
                      className="animate-slide-in"
                      style={{
                        backgroundColor: '#1e293b',
                        border: '1px solid #854d0e',
                        borderRadius: '0.625rem',
                        padding: '0.85rem',
                        boxShadow: '0 2px 8px rgba(245, 158, 11, 0.15)',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <span style={{ fontWeight: 600, color: '#f3f4f6', fontSize: '0.9rem' }}>
                            {task.userId}
                          </span>
                          <span
                            style={{
                              backgroundColor: '#78350f',
                              color: '#fef08a',
                              fontSize: '0.7rem',
                              padding: '0.15rem 0.4rem',
                              borderRadius: '9999px',
                              fontWeight: 600,
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.25rem',
                            }}
                          >
                            <span
                              style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#facc15' }}
                              className="animate-pulse-slow"
                            />
                            processing
                          </span>
                        </div>
                        <span style={{ fontSize: '1rem', fontWeight: 700, color: '#facc15' }}>
                          +${Number(task.amount).toFixed(2)}
                        </span>
                      </div>

                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          marginTop: '0.6rem',
                          paddingTop: '0.5rem',
                          borderTop: '1px solid #334155',
                          fontSize: '0.75rem',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#94a3b8' }}>
                          <Clock size={12} />
                          <span>{task.createdAt ? task.createdAt.toLocaleTimeString() : 'Just now'}</span>
                        </div>
                        <button
                          onClick={() => handleCopyTaskId(task.taskId)}
                          title="Copy Task ID"
                          style={{
                            background: 'none',
                            border: 'none',
                            color: copiedTaskId === task.taskId ? '#34d399' : '#94a3b8',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                            fontSize: '0.7rem',
                          }}
                        >
                          {copiedTaskId === task.taskId ? <Check size={12} /> : <Copy size={12} />}
                          <code>{task.taskId.slice(0, 8)}...</code>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* SECTION 2: Duplicate Rejections */}
          {(taskCategoryFilter === 'all' || taskCategoryFilter === 'duplicates') && (
            <div style={{ marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#f87171', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Rejected Duplicates ({duplicateTasks.length})
                </span>
                <span style={{ fontSize: '0.7rem', color: '#9ca3af' }}>Protected from double-charge</span>
              </div>

              {duplicateTasks.length === 0 ? (
                <div
                  style={{
                    backgroundColor: '#0b0f19',
                    borderRadius: '0.5rem',
                    padding: '0.85rem',
                    textAlign: 'center',
                    color: '#6b7280',
                    fontSize: '0.8rem',
                  }}
                >
                  No duplicate events detected.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  {duplicateTasks.map((task) => (
                    <div
                      key={task.taskId}
                      className="animate-slide-in"
                      style={{
                        backgroundColor: '#1c1313',
                        border: '1px solid #7f1d1d',
                        borderRadius: '0.625rem',
                        padding: '0.85rem',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <ShieldAlert size={16} color="#f87171" />
                          <span style={{ fontWeight: 600, color: '#fecaca', fontSize: '0.85rem' }}>
                            {task.userId}
                          </span>
                          <span
                            style={{
                              backgroundColor: '#450a0a',
                              color: '#f87171',
                              fontSize: '0.65rem',
                              padding: '0.1rem 0.4rem',
                              borderRadius: '9999px',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                            }}
                          >
                            duplicate rejected
                          </span>
                        </div>
                        <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#ef4444', textDecoration: 'line-through' }}>
                          +${Number(task.amount).toFixed(2)}
                        </span>
                      </div>

                      {/* Error Explanation */}
                      <p style={{ fontSize: '0.75rem', color: '#fca5a5', marginTop: '0.4rem', lineHeight: '1.3' }}>
                        {task.errorMessage || 'Duplicate submission detected within 5-minute window.'}
                      </p>

                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          marginTop: '0.5rem',
                          paddingTop: '0.4rem',
                          borderTop: '1px solid #371717',
                          fontSize: '0.7rem',
                          color: '#9ca3af',
                        }}
                      >
                        <span>Balance untouched</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span>{task.completedAt ? task.completedAt.toLocaleTimeString() : 'Rejected'}</span>
                          <button
                            onClick={() => handleCopyTaskId(task.taskId)}
                            style={{
                              background: 'none',
                              border: 'none',
                              color: copiedTaskId === task.taskId ? '#34d399' : '#6b7280',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.2rem',
                              fontSize: '0.65rem',
                            }}
                          >
                            <Copy size={10} />
                            <code>{task.taskId.slice(0, 6)}</code>
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* SECTION 3: Completed / Processed Credits History */}
          {(taskCategoryFilter === 'all' || taskCategoryFilter === 'processed') && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#10b981', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.6rem' }}>
                Successfully Processed ({processedTasks.length})
              </span>

              <div
                style={{
                  flex: 1,
                  overflowY: 'auto',
                  maxHeight: 280,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.6rem',
                  paddingRight: '0.25rem',
                }}
              >
                {processedTasks.length === 0 ? (
                  <div
                    style={{
                      backgroundColor: '#0b0f19',
                      borderRadius: '0.5rem',
                      padding: '1.25rem',
                      textAlign: 'center',
                      color: '#6b7280',
                      fontSize: '0.8rem',
                    }}
                  >
                    Completed credit tasks will appear here with fresh balance updates.
                  </div>
                ) : (
                  processedTasks.map((task) => (
                    <div
                      key={task.taskId}
                      className="animate-slide-in"
                      style={{
                        backgroundColor: '#0f172a',
                        border: '1px solid #1e293b',
                        borderRadius: '0.625rem',
                        padding: '0.75rem',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <CheckCircle2 size={15} color="#34d399" />
                          <span style={{ fontWeight: 600, color: '#f3f4f6', fontSize: '0.85rem' }}>
                            {task.userId}
                          </span>
                          <span
                            style={{
                              backgroundColor: '#064e3b',
                              color: '#6ee7b7',
                              fontSize: '0.65rem',
                              padding: '0.1rem 0.35rem',
                              borderRadius: '9999px',
                              fontWeight: 600,
                            }}
                          >
                            processed
                          </span>
                        </div>
                        <span style={{ fontSize: '0.95rem', fontWeight: 700, color: '#34d399' }}>
                          +${Number(task.amount).toFixed(2)}
                        </span>
                      </div>

                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          marginTop: '0.5rem',
                          fontSize: '0.7rem',
                          color: '#64748b',
                        }}
                      >
                        <span style={{ color: '#38bdf8', fontWeight: 600 }}>
                          {task.finalBalance !== undefined
                            ? `Updated Balance: $${Number(task.finalBalance).toFixed(2)}`
                            : 'Balance updated'}
                        </span>
                        <span>{task.completedAt ? task.completedAt.toLocaleTimeString() : 'Completed'}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </aside>
      </main>

      {/* Footer */}
      <footer
        style={{
          borderTop: '1px solid #1f2937',
          padding: '1rem',
          textAlign: 'center',
          color: '#6b7280',
          fontSize: '0.75rem',
          backgroundColor: '#0b0f19',
        }}
      >
        Basta Tech Lead Take-Home Exercise • Asynchronous Credit Processing Pipeline with Deduplication
      </footer>
    </div>
  );
}
