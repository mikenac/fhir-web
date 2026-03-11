import { createContext, useContext, useState, useEffect } from 'react';

// FHIR server configurations
export const FHIR_SERVERS = {
  smart: {
    id: 'smart',
    name: 'SMART Health IT',
    description: 'Public test server for healthcare app development',
    icon: '🏥',
  },
  hapi: {
    id: 'hapi',
    name: 'HAPI FHIR',
    description: 'Open source FHIR test server',
    icon: '🔬',
  },
  epic: {
    id: 'epic',
    name: 'Epic Sandbox',
    description: 'Epic FHIR sandbox (requires authentication)',
    icon: '🏢',
  },
};

const FHIRServerContext = createContext(null);

const LOCAL_STORAGE_KEY = 'fhir-server-selection';
const DEFAULT_SERVER = 'smart'; // Most reliable for demos

export function FHIRServerProvider({ children }) {
  // Initialize from localStorage or use default
  const [selectedServer, setSelectedServer] = useState(() => {
    const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
    return saved && FHIR_SERVERS[saved] ? saved : DEFAULT_SERVER;
  });

  // Persist to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEY, selectedServer);
  }, [selectedServer]);

  const value = {
    selectedServer,
    serverConfig: FHIR_SERVERS[selectedServer],
    setSelectedServer,
    availableServers: Object.values(FHIR_SERVERS),
  };

  return (
    <FHIRServerContext.Provider value={value}>
      {children}
    </FHIRServerContext.Provider>
  );
}

export function useFHIRServer() {
  const context = useContext(FHIRServerContext);
  if (!context) {
    throw new Error('useFHIRServer must be used within a FHIRServerProvider');
  }
  return context;
}
