import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { clinicalAPI } from '../api/client';
import { useFHIRServer } from '../contexts/FHIRServerContext';

function ClinicalData() {
  const [patientId, setPatientId] = useState('');
  const [activePatient, setActivePatient] = useState(null);

  const handleSearch = (e) => {
    e.preventDefault();
    if (patientId.trim()) {
      setActivePatient(patientId.trim());
    }
  };

  return (
    <div className="clinical-data">
      <h2>Clinical Data Query</h2>

      <form onSubmit={handleSearch} className="search-form">
        <div className="form-group">
          <label htmlFor="patientId">Patient ID</label>
          <input
            type="text"
            id="patientId"
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
            placeholder="Enter FHIR patient ID"
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={!patientId.trim()}>
          Load Clinical Data
        </button>
      </form>

      {activePatient && <ClinicalDataDisplay patientId={activePatient} />}
    </div>
  );
}

function ClinicalDataDisplay({ patientId }) {
  const { selectedServer } = useFHIRServer();

  const {
    data: encounters,
    isLoading: encountersLoading,
    error: encountersError,
  } = useQuery({
    queryKey: ['encounters', patientId, selectedServer],
    queryFn: async () => {
      const response = await clinicalAPI.getPatientEncounters(patientId, selectedServer);
      return response.data;
    },
  });

  const {
    data: orders,
    isLoading: ordersLoading,
    error: ordersError,
  } = useQuery({
    queryKey: ['orders', patientId, selectedServer],
    queryFn: async () => {
      const response = await clinicalAPI.getPatientOrders(patientId, selectedServer);
      return response.data;
    },
  });

  const {
    data: medications,
    isLoading: medicationsLoading,
    error: medicationsError,
  } = useQuery({
    queryKey: ['medications', patientId, selectedServer],
    queryFn: async () => {
      const response = await clinicalAPI.getPatientMedications(patientId, selectedServer);
      return response.data;
    },
  });

  const {
    data: referrals,
    isLoading: referralsLoading,
    error: referralsError,
  } = useQuery({
    queryKey: ['referrals', patientId, selectedServer],
    queryFn: async () => {
      const response = await clinicalAPI.getPatientReferrals(patientId, selectedServer);
      return response.data;
    },
  });

  return (
    <div className="clinical-display">
      <h3>Clinical Data for Patient: {patientId}</h3>

      <div className="data-grid">
        <DataSection
          title="Encounters"
          data={encounters}
          isLoading={encountersLoading}
          error={encountersError}
          renderItem={(encounter) => (
            <div key={encounter.id}>
              <p>
                <strong>Status:</strong> {encounter.status}
              </p>
              <p>
                <strong>Type:</strong> {encounter.type_display || encounter.class_code}
              </p>
              {encounter.period_start && (
                <p>
                  <strong>Date:</strong> {new Date(encounter.period_start).toLocaleString()}
                </p>
              )}
            </div>
          )}
        />

        <DataSection
          title="Orders"
          data={orders}
          isLoading={ordersLoading}
          error={ordersError}
          renderItem={(order) => (
            <div key={order.id}>
              <p>
                <strong>{order.code_display}</strong>
              </p>
              <p>
                Status: {order.status} | Intent: {order.intent}
              </p>
              {order.note && <p className="note">{order.note}</p>}
            </div>
          )}
        />

        <DataSection
          title="Medications"
          data={medications}
          isLoading={medicationsLoading}
          error={medicationsError}
          renderItem={(med) => (
            <div key={med.id}>
              <p>
                <strong>{med.code_display}</strong>
              </p>
              <p>
                Status: {med.status} | Intent: {med.intent}
              </p>
              {med.note && <p className="note">{med.note}</p>}
            </div>
          )}
        />

        <DataSection
          title="Referrals"
          data={referrals}
          isLoading={referralsLoading}
          error={referralsError}
          renderItem={(referral) => (
            <div key={referral.id}>
              <p>
                <strong>{referral.code_display}</strong>
              </p>
              <p>
                Status: {referral.status} | Intent: {referral.intent}
              </p>
              {referral.note && <p className="note">{referral.note}</p>}
            </div>
          )}
        />
      </div>
    </div>
  );
}

function DataSection({ title, data, isLoading, error, renderItem }) {
  return (
    <div className="data-section">
      <h4>{title}</h4>
      {isLoading && <p>Loading...</p>}
      {error && <p className="error">Error: {error.message}</p>}
      {data && data.total === 0 && <p className="no-data">No {title.toLowerCase()} found</p>}
      {data && data.total > 0 && (
        <div className="data-list">
          {data.results.map((item) => (
            <div key={item.id} className="data-item">
              {renderItem(item)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default ClinicalData;
