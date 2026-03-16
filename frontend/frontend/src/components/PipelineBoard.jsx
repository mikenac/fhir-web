import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { pipelineAPI, webhookAPI, clinicalAPI } from '../api/client';

const PRIORITY_COLORS = {
  stat:    { bg: '#fef2f2', text: '#991b1b' },
  asap:    { bg: '#fff7ed', text: '#9a3412' },
  urgent:  { bg: '#fffbeb', text: '#92400e' },
  routine: { bg: '#f0fdf4', text: '#166534' },
};

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDateTime(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  });
}

function formatDuration(seconds) {
  if (seconds == null) return '—';
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}

/**
 * Hardcoded test payload for the HAPI FHIR webhook demo.
 * Creates a ServiceRequest on HAPI that triggers a webhook back to the backend.
 */
const TEST_REFERRAL_PAYLOAD = {
  patient_id: 'example',
  requester_id: 'Practitioner/example',
  specialty_code: '394579002',
  specialty_display: 'Cardiology',
  intent: 'order',
  status: 'active',
  priority: 'routine',
  note: 'Test referral created via webhook demo',
};

export default function PipelineBoard() {
  const queryClient = useQueryClient();
  const [pipelineType, setPipelineType] = useState('incoming');
  const [selectedStageId, setSelectedStageId] = useState(null);
  const [selectedReferralId, setSelectedReferralId] = useState(null);
  const [moveToStageId, setMoveToStageId] = useState('');
  // Toast message shown after "Create Test Referral" succeeds
  const [toast, setToast] = useState(null);

  // Auto-dismiss toast after 4 seconds
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  // Webhook subscription status
  const { data: webhookStatus, isLoading: webhookStatusLoading } = useQuery({
    queryKey: ['webhookStatus'],
    queryFn: async () => {
      const res = await webhookAPI.status();
      return res.data;
    },
    // Poll every 10s so the UI self-corrects if the backend subscription drops
    refetchInterval: 10000,
  });

  const isSubscribed = webhookStatus?.active === true;

  // Subscribe mutation
  const subscribeMutation = useMutation({
    mutationFn: () => webhookAPI.subscribe(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhookStatus'] });
    },
    onError: (err) => {
      setToast(`Failed to subscribe: ${err.message}`);
    },
  });

  // Unsubscribe mutation
  const unsubscribeMutation = useMutation({
    mutationFn: () => webhookAPI.unsubscribe(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhookStatus'] });
    },
    onError: (err) => {
      setToast(`Failed to unsubscribe: ${err.message}`);
    },
  });

  // Create test referral on HAPI to fire a webhook
  const testReferralMutation = useMutation({
    mutationFn: () => clinicalAPI.createReferral(TEST_REFERRAL_PAYLOAD, 'hapi'),
    onSuccess: () => {
      setToast('Test referral created on HAPI — webhook should arrive shortly.');
      // Proactively refresh the board so the incoming referral appears
      queryClient.invalidateQueries({ queryKey: ['pipelineBoard'] });
      queryClient.invalidateQueries({ queryKey: ['stageReferrals'] });
    },
    onError: (err) => {
      setToast(`Failed to create test referral: ${err.message}`);
    },
  });

  // Board data (stages with counts).
  // Auto-refresh every 3s when subscribed so webhook-triggered cards appear quickly.
  const { data: boardData, isLoading: boardLoading } = useQuery({
    queryKey: ['pipelineBoard', pipelineType],
    queryFn: async () => {
      const res = await pipelineAPI.getBoard(pipelineType);
      return res.data;
    },
    refetchInterval: isSubscribed ? 3000 : false,
  });

  // Referrals in selected stage
  const { data: referralsData, isLoading: referralsLoading } = useQuery({
    queryKey: ['stageReferrals', pipelineType, selectedStageId],
    queryFn: async () => {
      const res = await pipelineAPI.listReferrals({
        pipeline_type: pipelineType,
        stage_id: selectedStageId,
        status: 'active',
        limit: 100,
      });
      return res.data;
    },
    enabled: !!selectedStageId,
  });

  // Selected referral detail
  const { data: referralDetail } = useQuery({
    queryKey: ['referralDetail', selectedReferralId],
    queryFn: async () => {
      const res = await pipelineAPI.getReferral(selectedReferralId);
      return res.data;
    },
    enabled: !!selectedReferralId,
  });

  // Transition history
  const { data: historyData } = useQuery({
    queryKey: ['referralHistory', selectedReferralId],
    queryFn: async () => {
      const res = await pipelineAPI.getHistory(selectedReferralId);
      return res.data;
    },
    enabled: !!selectedReferralId,
  });

  // Move referral mutation
  const moveMutation = useMutation({
    mutationFn: ({ referralId, toStageId }) =>
      pipelineAPI.createTransition(referralId, {
        to_stage_id: toStageId,
        outcome: 'advanced',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pipelineBoard'] });
      queryClient.invalidateQueries({ queryKey: ['stageReferrals'] });
      queryClient.invalidateQueries({ queryKey: ['referralDetail'] });
      queryClient.invalidateQueries({ queryKey: ['referralHistory'] });
      setMoveToStageId('');
    },
  });

  const handlePipelineToggle = (type) => {
    setPipelineType(type);
    setSelectedStageId(null);
    setSelectedReferralId(null);
  };

  const handleStageClick = (stageId) => {
    setSelectedStageId(stageId === selectedStageId ? null : stageId);
    setSelectedReferralId(null);
  };

  const handleReferralClick = (referralId) => {
    setSelectedReferralId(referralId === selectedReferralId ? null : referralId);
    setMoveToStageId('');
  };

  const handleMove = () => {
    if (!moveToStageId || !selectedReferralId) return;
    moveMutation.mutate({
      referralId: selectedReferralId,
      toStageId: moveToStageId,
    });
  };

  // Get the selected stage info from board data
  const selectedStage = boardData?.stages?.find((s) => s.id === selectedStageId);

  // Available target stages for moves (non-current, from same pipeline)
  const moveTargets = boardData?.stages?.filter(
    (s) => s.id !== selectedStageId && s.id !== referralDetail?.current_stage_id
  ) || [];

  return (
    <div className="pipeline-board">
      {/* Toast notification */}
      {toast && (
        <div
          role="status"
          aria-live="polite"
          style={{
            position: 'fixed',
            bottom: '1.5rem',
            right: '1.5rem',
            zIndex: 2000,
            background: testReferralMutation.isError ? '#fef2f2' : '#f0fdf4',
            border: `1px solid ${testReferralMutation.isError ? '#fecaca' : '#bbf7d0'}`,
            color: testReferralMutation.isError ? '#991b1b' : '#166534',
            borderRadius: 8,
            padding: '0.75rem 1.25rem',
            fontSize: '0.875rem',
            fontWeight: 500,
            boxShadow: 'var(--shadow-lg)',
            maxWidth: 360,
          }}
        >
          {toast}
        </div>
      )}

      {/* Header */}
      <div className="pipeline-header">
        <h2>Referral Pipeline</h2>
        <div className="pipeline-toggle">
          <button
            className={pipelineType === 'incoming' ? 'active' : ''}
            onClick={() => handlePipelineToggle('incoming')}
          >
            Referred To Us
          </button>
          <button
            className={pipelineType === 'outgoing' ? 'active' : ''}
            onClick={() => handlePipelineToggle('outgoing')}
          >
            Referring Out
          </button>
        </div>
      </div>

      {/* Webhook demo toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '0.75rem',
          padding: '0.625rem 1rem',
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          boxShadow: 'var(--shadow)',
        }}
      >
        {/* Subscription status pill */}
        <span
          aria-label={isSubscribed ? 'Webhook active' : 'Webhook inactive'}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            padding: '0.25rem 0.75rem',
            borderRadius: 999,
            fontSize: '0.78rem',
            fontWeight: 600,
            background: isSubscribed ? '#f0fdf4' : '#f1f5f9',
            color: isSubscribed ? '#166534' : 'var(--text-secondary)',
            border: `1px solid ${isSubscribed ? '#bbf7d0' : 'var(--border)'}`,
          }}
        >
          {/* Dot indicator */}
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: isSubscribed ? '#22c55e' : '#94a3b8',
              flexShrink: 0,
            }}
          />
          {webhookStatusLoading
            ? 'Checking...'
            : isSubscribed
            ? 'Listening for webhooks'
            : 'Not subscribed'}
        </span>

        {/* Subscribe / Unsubscribe toggle */}
        <button
          onClick={() =>
            isSubscribed ? unsubscribeMutation.mutate() : subscribeMutation.mutate()
          }
          disabled={subscribeMutation.isPending || unsubscribeMutation.isPending}
          style={{
            padding: '0.4rem 1rem',
            border: '1px solid var(--border)',
            borderRadius: 6,
            background: 'var(--surface)',
            color: 'var(--text-primary)',
            fontSize: '0.875rem',
            fontWeight: 500,
            cursor:
              subscribeMutation.isPending || unsubscribeMutation.isPending
                ? 'not-allowed'
                : 'pointer',
            opacity:
              subscribeMutation.isPending || unsubscribeMutation.isPending ? 0.6 : 1,
            transition: 'all 0.15s',
          }}
          onMouseEnter={(e) => {
            if (!e.currentTarget.disabled)
              e.currentTarget.style.borderColor = 'var(--primary-color)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)';
          }}
        >
          {subscribeMutation.isPending
            ? 'Subscribing...'
            : unsubscribeMutation.isPending
            ? 'Unsubscribing...'
            : isSubscribed
            ? 'Unsubscribe'
            : 'Subscribe to HAPI'}
        </button>

        {/* Divider */}
        <span
          aria-hidden="true"
          style={{ width: 1, height: 22, background: 'var(--border)', flexShrink: 0 }}
        />

        {/* Create test referral */}
        <button
          onClick={() => testReferralMutation.mutate()}
          disabled={!isSubscribed || testReferralMutation.isPending}
          title={
            !isSubscribed
              ? 'Subscribe to HAPI webhooks first'
              : 'Create a test ServiceRequest on HAPI to trigger a webhook'
          }
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.4rem',
            padding: '0.4rem 1rem',
            border: 'none',
            borderRadius: 6,
            background:
              !isSubscribed || testReferralMutation.isPending
                ? '#93c5fd'
                : 'var(--primary-color)',
            color: 'white',
            fontSize: '0.875rem',
            fontWeight: 500,
            cursor:
              !isSubscribed || testReferralMutation.isPending
                ? 'not-allowed'
                : 'pointer',
            transition: 'background 0.15s',
          }}
          onMouseEnter={(e) => {
            if (!e.currentTarget.disabled && isSubscribed)
              e.currentTarget.style.background = 'var(--primary-hover)';
          }}
          onMouseLeave={(e) => {
            if (isSubscribed && !testReferralMutation.isPending)
              e.currentTarget.style.background = 'var(--primary-color)';
          }}
        >
          <span aria-hidden="true">🧪</span>
          {testReferralMutation.isPending ? 'Creating...' : 'Create Test Referral'}
        </button>

        {/* Subscribe / unsubscribe error feedback */}
        {(subscribeMutation.isError || unsubscribeMutation.isError) && (
          <span style={{ fontSize: '0.78rem', color: 'var(--error-color)' }}>
            {subscribeMutation.error?.message || unsubscribeMutation.error?.message}
          </span>
        )}
      </div>

      {/* Stage columns */}
      {boardLoading ? (
        <div className="pipeline-empty">Loading stages...</div>
      ) : (
        <div className="pipeline-stages">
          {boardData?.stages?.map((stage, idx) => (
            <React.Fragment key={stage.id}>
              {idx > 0 && (
                <div className="pipeline-stage-arrow">
                  <svg viewBox="0 0 48 16" fill="none">
                    <line x1="0" y1="8" x2="38" y2="8" stroke="currentColor" strokeWidth="2" strokeDasharray="4 3" />
                    <polygon points="36,3 44,8 36,13" fill="currentColor" />
                  </svg>
                </div>
              )}
              <div
                className={`pipeline-stage-card${stage.id === selectedStageId ? ' selected' : ''}${stage.is_terminal ? ' terminal' : ''}`}
                onClick={() => handleStageClick(stage.id)}
              >
                <div className="stage-name">{stage.display_name}</div>
                <div className="stage-count">{stage.active_referral_count}</div>
              </div>
            </React.Fragment>
          ))}
        </div>
      )}

      {/* Referral list + detail panel */}
      {selectedStageId && (
        <div className={`pipeline-content${selectedReferralId ? ' with-detail' : ''}`}>
          {/* Referral table */}
          <div className="pipeline-referral-section">
            <div className="section-header">
              <h3>
                {selectedStage?.display_name || 'Stage'} Referrals
              </h3>
              {referralsData && (
                <span className="count-badge">{referralsData.total}</span>
              )}
            </div>

            {referralsLoading ? (
              <div className="pipeline-empty">Loading referrals...</div>
            ) : referralsData?.results?.length === 0 ? (
              <div className="pipeline-empty">
                <div className="empty-icon">📋</div>
                <div>No active referrals in this stage</div>
              </div>
            ) : (
              <table className="pipeline-table">
                <thead>
                  <tr>
                    <th>Patient</th>
                    <th>Requester</th>
                    <th>Specialty</th>
                    <th>Priority</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {referralsData?.results?.map((r) => (
                    <tr
                      key={r.id}
                      className={r.id === selectedReferralId ? 'selected-row' : ''}
                      onClick={() => handleReferralClick(r.id)}
                    >
                      <td style={{ fontWeight: 500 }}>
                        {r.patient_display || r.patient_id || '—'}
                      </td>
                      <td>{r.requester_display || '—'}</td>
                      <td>{r.specialty_display || '—'}</td>
                      <td>
                        {r.priority ? (
                          <span
                            className="priority-badge"
                            style={{
                              backgroundColor: PRIORITY_COLORS[r.priority]?.bg || '#f1f5f9',
                              color: PRIORITY_COLORS[r.priority]?.text || '#475569',
                            }}
                          >
                            {r.priority}
                          </span>
                        ) : '—'}
                      </td>
                      <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                        {formatDate(r.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Detail panel */}
          {selectedReferralId && referralDetail && (
            <div className="pipeline-detail-panel">
              <div className="detail-header">
                <h3>Referral Detail</h3>
                <button
                  className="detail-close"
                  onClick={() => setSelectedReferralId(null)}
                >
                  ×
                </button>
              </div>

              <div className="pipeline-detail-body">
                {/* Patient info */}
                <div className="detail-fields-grid">
                  <div className="detail-field">
                    <span className="field-label">Patient</span>
                    <span className="field-value">
                      {referralDetail.patient_display || '—'}
                    </span>
                  </div>
                  <div className="detail-field">
                    <span className="field-label">Status</span>
                    <span className="field-value" style={{ textTransform: 'capitalize' }}>
                      {referralDetail.status}
                    </span>
                  </div>
                  <div className="detail-field">
                    <span className="field-label">Stage</span>
                    <span className="field-value">
                      {referralDetail.current_stage_display_name}
                    </span>
                  </div>
                  <div className="detail-field">
                    <span className="field-label">Priority</span>
                    <span className="field-value" style={{ textTransform: 'capitalize' }}>
                      {referralDetail.priority || '—'}
                    </span>
                  </div>
                  <div className="detail-field">
                    <span className="field-label">Requester</span>
                    <span className="field-value">
                      {referralDetail.requester_display || '—'}
                    </span>
                  </div>
                  <div className="detail-field">
                    <span className="field-label">Performer</span>
                    <span className="field-value">
                      {referralDetail.performer_display || '—'}
                    </span>
                  </div>
                  <div className="detail-field">
                    <span className="field-label">Specialty</span>
                    <span className="field-value">
                      {referralDetail.specialty_display || '—'}
                    </span>
                  </div>
                  <div className="detail-field">
                    <span className="field-label">Source</span>
                    <span className="field-value">
                      {referralDetail.source === 'fhir_sync' ? 'FHIR Sync' : 'Manual'}
                    </span>
                  </div>
                </div>

                {referralDetail.note && (
                  <div className="detail-field">
                    <span className="field-label">Note</span>
                    <span className="field-value">{referralDetail.note}</span>
                  </div>
                )}

                <div className="detail-fields-grid">
                  <div className="detail-field">
                    <span className="field-label">Created</span>
                    <span className="field-value">
                      {formatDateTime(referralDetail.created_at)}
                    </span>
                  </div>
                  <div className="detail-field">
                    <span className="field-label">Authored</span>
                    <span className="field-value">
                      {formatDateTime(referralDetail.authored_on)}
                    </span>
                  </div>
                </div>

                {/* Transition history */}
                {historyData?.transitions?.length > 0 && (
                  <div className="pipeline-history">
                    <h4>Transition History</h4>
                    {historyData.transitions.map((t) => (
                      <div key={t.id} className="history-item">
                        <div
                          className={`history-dot${
                            t.outcome === 'completed' ? ' terminal' :
                            t.outcome === 'cancelled' ? ' cancelled' : ''
                          }`}
                        />
                        <div className="history-content">
                          <div className="history-stages">
                            {t.from_stage_display_name
                              ? `${t.from_stage_display_name} → ${t.to_stage_display_name}`
                              : `Entered ${t.to_stage_display_name}`
                            }
                          </div>
                          <div className="history-meta">
                            {formatDateTime(t.transitioned_at)}
                            {t.duration_seconds != null && ` · ${formatDuration(t.duration_seconds)}`}
                            {t.actor && ` · ${t.actor}`}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Move-to controls (only if not in terminal stage) */}
              {referralDetail && !boardData?.stages?.find(
                (s) => s.id === referralDetail.current_stage_id
              )?.is_terminal && (
                <div className="transition-controls">
                  <select
                    value={moveToStageId}
                    onChange={(e) => setMoveToStageId(e.target.value)}
                  >
                    <option value="">Move to...</option>
                    {moveTargets.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.display_name}
                      </option>
                    ))}
                  </select>
                  <button
                    className="btn-move"
                    onClick={handleMove}
                    disabled={!moveToStageId || moveMutation.isPending}
                  >
                    {moveMutation.isPending ? 'Moving...' : 'Move'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Prompt to select a stage */}
      {!selectedStageId && !boardLoading && (
        <div className="pipeline-empty">
          <div className="empty-icon">👆</div>
          <div>Select a stage above to view referrals</div>
        </div>
      )}
    </div>
  );
}
