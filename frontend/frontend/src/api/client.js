/**
 * API client for FHIR Web Service
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // Server responded with error
      console.error('API Error:', error.response.data);
      throw new Error(error.response.data.detail || 'An error occurred');
    } else if (error.request) {
      // Request made but no response
      console.error('Network Error:', error.request);
      throw new Error('Network error - please check your connection');
    } else {
      console.error('Error:', error.message);
      throw error;
    }
  }
);

// Patient API
export const patientAPI = {
  create: (demographics) => apiClient.post('/api/patients/', demographics),
  get: (patientId) => apiClient.get(`/api/patients/${patientId}`),
  getByMRN: (mrn, mrnSystem = 'http://hospital.example.org/mrn') =>
    apiClient.get(`/api/patients/mrn/${mrn}`, { params: { mrn_system: mrnSystem } }),
  search: (familyName, givenName, activeVisitsOnly = false, activeOrdersOnly = false) =>
    apiClient.get('/api/patients/', {
      params: {
        family_name: familyName,
        given_name: givenName,
        active_visits_only: activeVisitsOnly,
        active_orders_only: activeOrdersOnly
      }
    }),
  update: (patientId, demographics) => apiClient.put(`/api/patients/${patientId}`, demographics),
};

// Clinical API
export const clinicalAPI = {
  // Encounters
  createEncounter: (encounter) => apiClient.post('/api/clinical/encounters', encounter),
  getEncounter: (encounterId) => apiClient.get(`/api/clinical/encounters/${encounterId}`),
  getPatientEncounters: (patientId) =>
    apiClient.get(`/api/clinical/patients/${patientId}/encounters`),

  // Orders
  createOrder: (order) => apiClient.post('/api/clinical/orders', order),
  getPatientOrders: (patientId) => apiClient.get(`/api/clinical/patients/${patientId}/orders`),

  // Medications
  createMedication: (medication) => apiClient.post('/api/clinical/medications', medication),
  getPatientMedications: (patientId) =>
    apiClient.get(`/api/clinical/patients/${patientId}/medications`),

  // Referrals
  createReferral: (referral) => apiClient.post('/api/clinical/referrals', referral),
  getPatientReferrals: (patientId) =>
    apiClient.get(`/api/clinical/patients/${patientId}/referrals`),
};

// Operational API
export const operationalAPI = {
  // Practitioners
  createPractitioner: (practitioner) =>
    apiClient.post('/api/operational/practitioners', practitioner),
  getPractitioner: (practitionerId) =>
    apiClient.get(`/api/operational/practitioners/${practitionerId}`),
  getPractitionerByNPI: (npi) => apiClient.get(`/api/operational/practitioners/npi/${npi}`),

  // Coverage
  createCoverage: (coverage) => apiClient.post('/api/operational/coverage', coverage),
  getPatientCoverage: (patientId) =>
    apiClient.get(`/api/operational/patients/${patientId}/coverage`),

  // Scheduling
  createSchedule: (schedule) => apiClient.post('/api/operational/schedules', schedule),
  getPractitionerSchedules: (practitionerId) =>
    apiClient.get(`/api/operational/practitioners/${practitionerId}/schedules`),
  createSlot: (slot) => apiClient.post('/api/operational/slots', slot),
  getScheduleSlots: (scheduleId) => apiClient.get(`/api/operational/schedules/${scheduleId}/slots`),
};

// Health check
export const healthAPI = {
  check: () => apiClient.get('/health'),
};

export default apiClient;
