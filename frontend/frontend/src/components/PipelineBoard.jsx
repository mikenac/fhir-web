import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
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
 * Preset FHIR server options for webhook subscriptions.
 * Users can switch between the public HAPI cloud server and a local Docker instance.
 */
const WEBHOOK_FHIR_SERVERS = [
  { id: 'hapi-public', label: 'HAPI Public', url: 'https://hapi.fhir.org/baseR4' },
  { id: 'hapi-local', label: 'HAPI Local (Docker)', url: 'http://localhost:8090/fhir' },
];

/**
 * Payload used when routing the test referral through the backend's
 * createReferral endpoint (public HAPI path).
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

/**
 * Post a minimal ServiceRequest directly to a FHIR server.
 * Used for the local Docker HAPI target, which the backend proxy doesn't route to.
 * @param {string} fhirUrl - Base URL of the FHIR server (e.g. 'http://localhost:8090/fhir')
 * @returns {Promise} Axios promise resolving to the created resource
 */
const createTestReferralOnServer = (fhirUrl) => {
  const payload = {
    resourceType: 'ServiceRequest',
    status: 'active',
    intent: 'order',
    subject: { reference: 'Patient/test123', display: 'Test Patient' },
    requester: { display: 'Dr. Smith' },
    code: {
      coding: [{ system: 'http://snomed.info/sct', code: '394579002', display: 'Cardiology' }],
    },
    priority: 'routine',
    note: [{ text: 'Test referral created via webhook demo' }],
  };
  // Post directly to the FHIR server — bypasses the FastAPI backend
  return axios.post(`${fhirUrl}/ServiceRequest`, payload, {
    headers: { 'Content-Type': 'application/fhir+json' },
  });
};

export default function PipelineBoard() {
  const queryClient = useQueryClient();
  const [pipelineType, setPipelineType] = useState('incoming');
  const [selectedStageId, setSelectedStageId] = useState(null);
  const [selectedReferralId, setSelectedReferralId] = useState(null);
  const [moveToStageId, setMoveToStageId] = useState('');
  // Toast message shown after "Create Test Referral" succeeds
  const [toast, setToast] = useState(null);
  // Which FHIR server to subscribe to for webhooks — defaults to public HAPI
  const [webhookFhirUrl, setWebhookFhirUrl] = useState(WEBHOOK_FHIR_SERVERS[0].url);

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

  // Subscribe mutation — passes the currently selected FHIR server URL
  const subscribeMutation = useMutation({
    mutationFn: () => webhookAPI.subscribe(webhookFhirUrl),
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

  // Create test referral on the selected FHIR server to fire a webhook.
  // When targeting local HAPI the request goes directly to the Docker instance;
  // when targeting public HAPI it routes through the backend proxy as before.
  const testReferralMutation = useMutation({
    mutationFn: () => {
      const isLocal = webhookFhirUrl.includes('localhost');
      if (isLocal) {
        // Direct POST — backend proxy doesn't know about the local Docker URL
        return createTestReferralOnServer(webhookFhirUrl);
      }
      // Route through the backend for public HAPI so auth/logging applies
      return clinicalAPI.createReferral(TEST_REFERRAL_PAYLOAD, 'hapi');
    },
    onSuccess: () => {
      const serverLabel = WEBHOOK_FHIR_SERVERS.find((s) => s.url === webhookFhirUrl)?.label ?? webhookFhirUrl;
      setToast(`Test referral created on ${serverLabel} — webhook should arrive shortly.`);
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

      {/* Webhook demo toolbar
          Layout: [FHIR Server select] [Subscribe/Unsubscribe btn] [status pill] | [Create Test Referral btn]
      */}
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
        {/* FHIR server selector
            Disabled while subscribed — changing mid-subscription would be confusing
            because the existing subscription still points at the old server. */}
        <select
          value={webhookFhirUrl}
          onChange={(e) => setWebhookFhirUrl(e.target.value)}
          disabled={isSubscribed}
          aria-label="Webhook target FHIR server"
          title={isSubscribed ? 'Unsubscribe before changing the target server' : 'Select FHIR server for webhook subscriptions'}
          style={{
            padding: '0.35rem 0.6rem',
            border: '1px solid var(--border)',
            borderRadius: 6,
            background: isSubscribed ? '#f1f5f9' : 'var(--surface)',
            color: isSubscribed ? 'var(--text-secondary)' : 'var(--text-primary)',
            fontSize: '0.8rem',
            fontWeight: 500,
            cursor: isSubscribed ? 'not-allowed' : 'pointer',
            minWidth: 160,
          }}
        >
          {WEBHOOK_FHIR_SERVERS.map((server) => (
            <option key={server.id} value={server.url}>
              {server.label}
            </option>
          ))}
        </select>

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
            : 'Subscribe'}
        </button>

        {/* Subscription status pill
            When subscribed, shows which server is actually receiving events
            (sourced from the backend status response). */}
        <span
          aria-label={isSubscribed ? 'Webhook active' : 'Webhook inactive'}
          title={isSubscribed && webhookStatus?.fhir_server ? `Subscribed to: ${webhookStatus.fhir_server}` : undefined}
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
          {/* Animated dot */}
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
            ? `Listening · ${WEBHOOK_FHIR_SERVERS.find((s) => s.url === webhookStatus?.fhir_server)?.label ?? 'Custom'}`
            : 'Not subscribed'}
        </span>

        {/* Divider */}
        <span
          aria-hidden="true"
          style={{ width: 1, height: 22, background: 'var(--border)', flexShrink: 0 }}
        />

        {/* Create test referral
            Routes directly to the FHIR server if targeting localhost,
            otherwise goes through the backend proxy. */}
        <button
          onClick={() => testReferralMutation.mutate()}
          disabled={!isSubscribed || testReferralMutation.isPending}
          title={
            !isSubscribed
              ? 'Subscribe to FHIR webhooks first'
              : `Create a test ServiceRequest on ${WEBHOOK_FHIR_SERVERS.find((s) => s.url === webhookFhirUrl)?.label ?? 'selected server'} to trigger a webhook`
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
