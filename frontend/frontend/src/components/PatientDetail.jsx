import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams, Link } from 'react-router-dom';
import { patientAPI, clinicalAPI } from '../api/client';
import { useFHIRServer } from '../contexts/FHIRServerContext';

function PatientDetail() {
  const { patientId } = useParams();
  const { selectedServer } = useFHIRServer();
  const [activeTab, setActiveTab] = useState('encounters');

  const {
    data: patient,
    isLoading: patientLoading,
    error: patientError,
  } = useQuery({
    queryKey: ['patient', patientId, selectedServer],
    queryFn: async () => {
      const response = await patientAPI.get(patientId, selectedServer);
      return response.data;
    },
  });

  const {
    data: encounters,
    isLoading: encountersLoading,
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
  } = useQuery({
    queryKey: ['medications', patientId, selectedServer],
    queryFn: async () => {
      const response = await clinicalAPI.getPatientMedications(patientId, selectedServer);
      return response.data;
    },
  });

  if (patientLoading) return <div className="loading">Loading patient...</div>;
  if (patientError) return <div className="error">Error: {patientError.message}</div>;

  return (
    <div className="patient-detail">
      <div className="patient-header">
        <Link to="/" className="back-link">
          ← Back to Search
        </Link>
        <h2>Patient Details</h2>
      </div>

      <div className="patient-detail-grid">
        <div className="patient-info-column">
          <div className="patient-info-card">
            <h3>{patient.full_name}</h3>
            <div className="info-grid">
              <div className="info-item">
                <strong>Patient ID:</strong>
                <span>{patient.id}</span>
              </div>
              <div className="info-item">
                <strong>MRN:</strong>
                <span>{patient.mrn}</span>
              </div>
              <div className="info-item">
                <strong>Birth Date:</strong>
                <span>{patient.birth_date}</span>
              </div>
              {patient.gender && (
                <div className="info-item">
                  <strong>Gender:</strong>
                  <span>{patient.gender}</span>
                </div>
              )}
              {patient.phone && (
                <div className="info-item">
                  <strong>Phone:</strong>
                  <span>{patient.phone}</span>
                </div>
              )}
              {patient.email && (
                <div className="info-item">
                  <strong>Email:</strong>
                  <span>{patient.email}</span>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="clinical-data-column">
          <div className="clinical-tabs">
            <button
              className={`clinical-tab${activeTab === 'encounters' ? ' active' : ''}`}
              onClick={() => setActiveTab('encounters')}
            >
              Encounters
              {encounters && <span className="tab-badge">{encounters.total}</span>}
            </button>
            <button
              className={`clinical-tab${activeTab === 'orders' ? ' active' : ''}`}
              onClick={() => setActiveTab('orders')}
            >
              Orders
              {orders && <span className="tab-badge">{orders.total}</span>}
            </button>
            <button
              className={`clinical-tab${activeTab === 'medications' ? ' active' : ''}`}
              onClick={() => setActiveTab('medications')}
            >
              Medications
              {medications && <span className="tab-badge">{medications.total}</span>}
            </button>
          </div>

          <div className="clinical-tab-content">
            {activeTab === 'encounters' && (
              <div className="data-section">
                {encountersLoading ? (
                  <p>Loading encounters...</p>
                ) : encounters && encounters.total > 0 ? (
                  <div className="data-list">
                    {encounters.results.map((encounter) => (
                      <div key={encounter.id} className="data-item">
                        <p>
                          <strong>Status:</strong> {encounter.status}
                        </p>
                        <p>
                          <strong>Type:</strong> {encounter.type_display || encounter.class_code}
                        </p>
                        {encounter.period_start && (
                          <p>
                            <strong>Date:</strong> {new Date(encounter.period_start).toLocaleDateString()}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="no-data">No encounters found</p>
                )}
              </div>
            )}

            {activeTab === 'orders' && (
              <div className="data-section">
                {ordersLoading ? (
                  <p>Loading orders...</p>
                ) : orders && orders.total > 0 ? (
                  <div className="data-list">
                    {orders.results.map((order) => (
                      <div key={order.id} className="data-item">
                        <p>
                          <strong>{order.code_display}</strong>
                        </p>
                        <p>
                          <strong>Status:</strong> {order.status}
                        </p>
                        {order.note && <p className="note">{order.note}</p>}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="no-data">No orders found</p>
                )}
              </div>
            )}

            {activeTab === 'medications' && (
              <div className="data-section">
                {medicationsLoading ? (
                  <p>Loading medications...</p>
                ) : medications && medications.total > 0 ? (
                  <div className="data-list">
                    {medications.results.map((med) => (
                      <div key={med.id} className="data-item">
                        <p>
                          <strong>{med.code_display}</strong>
                        </p>
                        <p>
                          <strong>Status:</strong> {med.status}
                        </p>
                        {med.note && <p className="note">{med.note}</p>}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="no-data">No medications found</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default PatientDetail;
