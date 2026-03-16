import { useState, useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, Link } from 'react-router-dom';
import { operationalAPI } from '../api/client';
import { useFHIRServer } from '../contexts/FHIRServerContext';

/**
 * Color map for FHIR ServiceRequest statuses.
 * Each entry is [bg, text, ring] for the status badge.
 */
const STATUS_COLORS = {
  active:             { bg: '#dbeafe', text: '#1e40af', dot: '#3b82f6' },
  completed:          { bg: '#dcfce7', text: '#166534', dot: '#22c55e' },
  revoked:            { bg: '#fef2f2', text: '#991b1b', dot: '#ef4444' },
  'on-hold':          { bg: '#fef9c3', text: '#854d0e', dot: '#eab308' },
  draft:              { bg: '#f3f4f6', text: '#374151', dot: '#9ca3af' },
  'entered-in-error': { bg: '#fef2f2', text: '#991b1b', dot: '#f87171' },
  unknown:            { bg: '#f3f4f6', text: '#6b7280', dot: '#9ca3af' },
};

/** Priority styling */
const PRIORITY_COLORS = {
  stat:    { bg: '#fef2f2', text: '#991b1b' },
  asap:    { bg: '#fff7ed', text: '#9a3412' },
  urgent:  { bg: '#fef9c3', text: '#854d0e' },
  routine: { bg: '#f3f4f6', text: '#6b7280' },
};

/** All FHIR ServiceRequest statuses */
const ALL_STATUSES = ['draft', 'active', 'on-hold', 'revoked', 'completed', 'entered-in-error', 'unknown'];

/**
 * Referral Dashboard — cross-patient referral tracking view.
 * Shows all ServiceRequests from the selected FHIR server with
 * status metrics, filtering, searching, and sorting.
 */
function ReferralDashboard() {
  const navigate = useNavigate();
  const { selectedServer, serverConfig } = useFHIRServer();

  // Filter state
  const [statusFilter, setStatusFilter] = useState('');
  const [searchText, setSearchText] = useState('');
  const [authoredAfter, setAuthoredAfter] = useState('');
  const [authoredBefore, setAuthoredBefore] = useState('');
  const [sortField, setSortField] = useState('authored_on');
  const [sortDirection, setSortDirection] = useState('desc');

  // Debounce search text
  const [debouncedSearch, setDebouncedSearch] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchText), 300);
    return () => clearTimeout(timer);
  }, [searchText]);

  // API filters (server-side)
  const apiFilters = useMemo(() => ({
    status: statusFilter || undefined,
    authoredAfter: authoredAfter || undefined,
    authoredBefore: authoredBefore || undefined,
  }), [statusFilter, authoredAfter, authoredBefore]);

  // Fetch dashboard data
  const { data, isLoading, error } = useQuery({
    queryKey: ['referralDashboard', apiFilters, selectedServer],
    queryFn: async () => {
      const response = await operationalAPI.getReferralDashboard(apiFilters, selectedServer);
      return response.data;
    },
    placeholderData: (prev) => prev,
  });

  // Client-side text search filtering
  const filteredResults = useMemo(() => {
    if (!data?.results) return [];
    if (!debouncedSearch) return data.results;
    const q = debouncedSearch.toLowerCase();
    return data.results.filter((r) =>
      (r.patient_display || '').toLowerCase().includes(q) ||
      r.patient_id.toLowerCase().includes(q) ||
      r.code_display.toLowerCase().includes(q) ||
      (r.requester_display || '').toLowerCase().includes(q)
    );
  }, [data?.results, debouncedSearch]);

  // Client-side sorting
  const sortedResults = useMemo(() => {
    const sorted = [...filteredResults];
    sorted.sort((a, b) => {
      let aVal = a[sortField] || '';
      let bVal = b[sortField] || '';
      if (sortField === 'authored_on') {
        aVal = aVal ? new Date(aVal).getTime() : 0;
        bVal = bVal ? new Date(bVal).getTime() : 0;
      }
      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [filteredResults, sortField, sortDirection]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const sortIcon = (field) => {
    if (sortField !== field) return ' \u2195';
    return sortDirection === 'asc' ? ' \u2191' : ' \u2193';
  };

  const handleStatusCardClick = (s) => {
    setStatusFilter((cur) => (cur === s ? '' : s));
  };

  const clearFilters = () => {
    setStatusFilter('');
    setSearchText('');
    setAuthoredAfter('');
    setAuthoredBefore('');
  };

  const hasActiveFilters = statusFilter || searchText || authoredAfter || authoredBefore;

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* Breadcrumb + header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
          <Link to="/" className="back-link" style={{ fontSize: '0.85rem' }}>Home</Link>
          <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>/</span>
          <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Referral Dashboard</span>
        </div>
        <h2 style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
          Referral Dashboard
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: 4 }}>
          Tracking referrals from {serverConfig.name}
        </p>
      </div>

      {/* Status Metric Cards */}
      {data?.status_counts && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
          gap: 12,
          marginBottom: 24,
        }}>
          {ALL_STATUSES.map((s) => {
            const count = data.status_counts[s] || 0;
            const isActive = statusFilter === s;
            const colors = STATUS_COLORS[s] || STATUS_COLORS.unknown;
            return (
              <button
                key={s}
                onClick={() => handleStatusCardClick(s)}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  padding: '16px 8px',
                  borderRadius: 10,
                  border: isActive ? `2px solid ${colors.dot}` : '2px solid var(--border)',
                  background: isActive ? colors.bg : 'var(--surface)',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  boxShadow: isActive ? `0 0 0 3px ${colors.dot}22` : 'none',
                }}
              >
                <span style={{
                  fontSize: '1.75rem',
                  fontWeight: 700,
                  color: count > 0 ? colors.text : 'var(--text-secondary)',
                  lineHeight: 1,
                }}>
                  {count}
                </span>
                <span style={{
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  color: 'var(--text-secondary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                  marginTop: 6,
                }}>
                  {s}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* Filter Bar */}
      <div style={{
        background: 'var(--surface)',
        borderRadius: 10,
        border: '1px solid var(--border)',
        padding: '16px 20px',
        marginBottom: 24,
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'flex-end',
        gap: 16,
      }}>
        {/* Status dropdown */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label htmlFor="status-filter" style={{
            fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-secondary)',
            textTransform: 'uppercase', letterSpacing: '0.5px',
          }}>Status</label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: '0.9rem',
              background: 'var(--surface)',
              color: 'var(--text-primary)',
              minWidth: 140,
            }}
          >
            <option value="">All Statuses</option>
            {ALL_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        {/* Search */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1, minWidth: 200 }}>
          <label htmlFor="search-text" style={{
            fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-secondary)',
            textTransform: 'uppercase', letterSpacing: '0.5px',
          }}>Search</label>
          <input
            id="search-text"
            type="text"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Patient name, ID, or specialty..."
            style={{
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: '0.9rem',
              background: 'var(--surface)',
              color: 'var(--text-primary)',
            }}
          />
        </div>

        {/* Date range */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label htmlFor="date-from" style={{
            fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-secondary)',
            textTransform: 'uppercase', letterSpacing: '0.5px',
          }}>From</label>
          <input
            id="date-from"
            type="date"
            value={authoredAfter}
            onChange={(e) => setAuthoredAfter(e.target.value)}
            style={{
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: '0.9rem',
              background: 'var(--surface)',
              color: 'var(--text-primary)',
            }}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label htmlFor="date-to" style={{
            fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-secondary)',
            textTransform: 'uppercase', letterSpacing: '0.5px',
          }}>To</label>
          <input
            id="date-to"
            type="date"
            value={authoredBefore}
            onChange={(e) => setAuthoredBefore(e.target.value)}
            style={{
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: '0.9rem',
              background: 'var(--surface)',
              color: 'var(--text-primary)',
            }}
          />
        </div>

        {/* Clear */}
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="btn btn-secondary"
            style={{ padding: '8px 16px', fontSize: '0.85rem' }}
          >
            Clear Filters
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="error-box" style={{ marginBottom: 24 }}>
          <h3>Failed to load referrals</h3>
          <p>{error.message}</p>
        </div>
      )}

      {/* Loading */}
      {isLoading && !data && (
        <div className="loading-state">
          <p>Loading referrals from {serverConfig.name}...</p>
        </div>
      )}

      {/* Empty */}
      {data && sortedResults.length === 0 && !isLoading && (
        <div className="empty-state">
          <p style={{ fontSize: '1.1rem', fontWeight: 500, marginBottom: 4 }}>No referrals found</p>
          <p style={{ fontSize: '0.9rem' }}>
            {hasActiveFilters
              ? 'Try adjusting your filters'
              : `No ServiceRequest resources found on ${serverConfig.name}`
            }
          </p>
        </div>
      )}

      {/* Referral Table */}
      {sortedResults.length > 0 && (
        <div style={{
          background: 'var(--surface)',
          borderRadius: 10,
          border: '1px solid var(--border)',
          boxShadow: 'var(--shadow)',
          overflow: 'hidden',
        }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  {[
                    { key: 'patient_display', label: 'Patient' },
                    { key: 'code_display', label: 'Specialty' },
                    { key: 'status', label: 'Status' },
                    { key: 'priority', label: 'Priority' },
                    { key: 'authored_on', label: 'Date' },
                    { key: null, label: 'Referring Provider' },
                    { key: null, label: 'Notes' },
                  ].map(({ key, label }) => (
                    <th
                      key={label}
                      onClick={key ? () => handleSort(key) : undefined}
                      style={{
                        textAlign: 'left',
                        padding: '12px 16px',
                        fontSize: '0.7rem',
                        fontWeight: 600,
                        color: 'var(--text-secondary)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px',
                        background: 'var(--background)',
                        cursor: key ? 'pointer' : 'default',
                        userSelect: 'none',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {label}{key ? sortIcon(key) : ''}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedResults.map((referral, idx) => {
                  const statusColor = STATUS_COLORS[referral.status] || STATUS_COLORS.unknown;
                  const priorityColor = referral.priority
                    ? (PRIORITY_COLORS[referral.priority] || PRIORITY_COLORS.routine)
                    : null;

                  return (
                    <tr
                      key={referral.id}
                      style={{
                        borderBottom: idx < sortedResults.length - 1 ? '1px solid var(--border)' : 'none',
                        transition: 'background 0.1s',
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.background = 'var(--background)'}
                      onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                    >
                      {/* Patient */}
                      <td style={{ padding: '12px 16px' }}>
                        <button
                          onClick={() => navigate(`/patients/${referral.patient_id}`)}
                          style={{
                            background: 'none',
                            border: 'none',
                            padding: 0,
                            color: 'var(--primary-color)',
                            fontWeight: 500,
                            cursor: 'pointer',
                            fontSize: '0.9rem',
                            textAlign: 'left',
                          }}
                          onMouseEnter={(e) => e.target.style.textDecoration = 'underline'}
                          onMouseLeave={(e) => e.target.style.textDecoration = 'none'}
                        >
                          {referral.patient_display || referral.patient_id}
                        </button>
                      </td>

                      {/* Specialty */}
                      <td style={{ padding: '12px 16px', color: 'var(--text-primary)', fontWeight: 500 }}>
                        {referral.code_display || <span style={{ color: 'var(--text-secondary)' }}>-</span>}
                      </td>

                      {/* Status badge */}
                      <td style={{ padding: '12px 16px' }}>
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 6,
                          padding: '4px 10px',
                          borderRadius: 999,
                          fontSize: '0.78rem',
                          fontWeight: 600,
                          background: statusColor.bg,
                          color: statusColor.text,
                        }}>
                          <span style={{
                            width: 7,
                            height: 7,
                            borderRadius: '50%',
                            background: statusColor.dot,
                            flexShrink: 0,
                          }} />
                          {referral.status}
                        </span>
                      </td>

                      {/* Priority */}
                      <td style={{ padding: '12px 16px' }}>
                        {priorityColor ? (
                          <span style={{
                            display: 'inline-block',
                            padding: '3px 10px',
                            borderRadius: 999,
                            fontSize: '0.78rem',
                            fontWeight: 500,
                            background: priorityColor.bg,
                            color: priorityColor.text,
                            textTransform: 'capitalize',
                          }}>
                            {referral.priority}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--text-secondary)' }}>-</span>
                        )}
                      </td>

                      {/* Date */}
                      <td style={{ padding: '12px 16px', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                        {referral.authored_on
                          ? new Date(referral.authored_on).toLocaleDateString()
                          : '-'}
                      </td>

                      {/* Referring provider */}
                      <td style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>
                        {referral.requester_display || '-'}
                      </td>

                      {/* Notes */}
                      <td style={{
                        padding: '12px 16px',
                        color: 'var(--text-secondary)',
                        maxWidth: 220,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }} title={referral.note || ''}>
                        {referral.note || '-'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Footer */}
          <div style={{
            borderTop: '1px solid var(--border)',
            padding: '10px 16px',
            background: 'var(--background)',
            fontSize: '0.8rem',
            color: 'var(--text-secondary)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <span>
              Showing {sortedResults.length} of {data?.total || 0} referral{data?.total !== 1 ? 's' : ''}
              {debouncedSearch && ` matching "${debouncedSearch}"`}
            </span>
            {isLoading && <span style={{ color: 'var(--primary-color)' }}>Updating...</span>}
          </div>
        </div>
      )}
    </div>
  );
}

export default ReferralDashboard;
