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

/**
 * Helper function to add server parameter to request config
 * @param {string|null} server - The FHIR server to use (smart, hapi, epic)
 * @param {object} config - Existing request config
 * @returns {object} Updated config with server parameter
 */
function addServerParam(server, config = {}) {
  if (!server) return config;

  return {
    ...config,
    params: {
      ...config.params,
      server,
    },
  };
}

// Patient API
export const patientAPI = {
  create: (demographics, server = null) =>
    apiClient.post('/api/patients/', demographics, addServerParam(server)),
  get: (patientId, server = null) =>
    apiClient.get(`/api/patients/${patientId}`, addServerParam(server)),
  getByMRN: (mrn, mrnSystem = 'http://hospital.example.org/mrn', server = null) =>
    apiClient.get(`/api/patients/mrn/${mrn}`, addServerParam(server, { params: { mrn_system: mrnSystem } })),
  search: (familyName, givenName, server = null) =>
    apiClient.get('/api/patients/', addServerParam(server, { params: { family_name: familyName, given_name: givenName } })),
  update: (patientId, demographics, server = null) =>
    apiClient.put(`/api/patients/${patientId}`, demographics, addServerParam(server)),
};

// Clinical API
export const clinicalAPI = {
  // Encounters
  createEncounter: (encounter, server = null) =>
    apiClient.post('/api/clinical/encounters', encounter, addServerParam(server)),
  getEncounter: (encounterId, server = null) =>
    apiClient.get(`/api/clinical/encounters/${encounterId}`, addServerParam(server)),
  getPatientEncounters: (patientId, server = null) =>
    apiClient.get(`/api/clinical/patients/${patientId}/encounters`, addServerParam(server)),

  // Orders
  createOrder: (order, server = null) =>
    apiClient.post('/api/clinical/orders', order, addServerParam(server)),
  getPatientOrders: (patientId, server = null) =>
    apiClient.get(`/api/clinical/patients/${patientId}/orders`, addServerParam(server)),

  // Medications
  createMedication: (medication, server = null) =>
    apiClient.post('/api/clinical/medications', medication, addServerParam(server)),
  getPatientMedications: (patientId, server = null) =>
    apiClient.get(`/api/clinical/patients/${patientId}/medications`, addServerParam(server)),

  // Referrals
  createReferral: (referral, server = null) =>
    apiClient.post('/api/clinical/referrals', referral, addServerParam(server)),
  getPatientReferrals: (patientId, server = null) =>
    apiClient.get(`/api/clinical/patients/${patientId}/referrals`, addServerParam(server)),
};

// Operational API
export const operationalAPI = {
  // Server configuration
  getAvailableServers: () => apiClient.get('/api/operational/servers'),

  // Practitioners
  createPractitioner: (practitioner, server = null) =>
    apiClient.post('/api/operational/practitioners', practitioner, addServerParam(server)),
  getPractitioner: (practitionerId, server = null) =>
    apiClient.get(`/api/operational/practitioners/${practitionerId}`, addServerParam(server)),
  getPractitionerByNPI: (npi, server = null) =>
    apiClient.get(`/api/operational/practitioners/npi/${npi}`, addServerParam(server)),

  // Coverage
  createCoverage: (coverage, server = null) =>
    apiClient.post('/api/operational/coverage', coverage, addServerParam(server)),
  getPatientCoverage: (patientId, server = null) =>
    apiClient.get(`/api/operational/patients/${patientId}/coverage`, addServerParam(server)),

  // Scheduling
  createSchedule: (schedule, server = null) =>
    apiClient.post('/api/operational/schedules', schedule, addServerParam(server)),
  getPractitionerSchedules: (practitionerId, server = null) =>
    apiClient.get(`/api/operational/practitioners/${practitionerId}/schedules`, addServerParam(server)),
  createSlot: (slot, server = null) =>
    apiClient.post('/api/operational/slots', slot, addServerParam(server)),
  getScheduleSlots: (scheduleId, server = null) =>
    apiClient.get(`/api/operational/schedules/${scheduleId}/slots`, addServerParam(server)),
};

// Health check
export const healthAPI = {
  check: () => apiClient.get('/health'),
};

export default apiClient;
