import { useState } from 'react';
import { useFHIRServer } from '../contexts/FHIRServerContext';
import { useQueryClient } from '@tanstack/react-query';

export default function ServerSelector() {
  const { selectedServer, serverConfig, setSelectedServer, availableServers } = useFHIRServer();
  const [isOpen, setIsOpen] = useState(false);
  const queryClient = useQueryClient();

  const handleServerChange = (serverId) => {
    // Clear React Query cache when switching servers
    queryClient.clear();
    setSelectedServer(serverId);
    setIsOpen(false);
  };

  return (
    <div className="server-selector">
      <button
        className="server-selector-button"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Select FHIR Server"
      >
        <span className="server-icon">{serverConfig.icon}</span>
        <span className="server-name">{serverConfig.name}</span>
        <span className="dropdown-arrow">{isOpen ? '▲' : '▼'}</span>
      </button>

      {isOpen && (
        <div className="server-dropdown">
          {availableServers.map((server) => (
            <button
              key={server.id}
              className={`server-option ${selectedServer === server.id ? 'selected' : ''}`}
              onClick={() => handleServerChange(server.id)}
            >
              <span className="server-icon">{server.icon}</span>
              <div className="server-info">
                <div className="server-option-name">{server.name}</div>
                <div className="server-option-desc">{server.description}</div>
              </div>
              {selectedServer === server.id && <span className="check-mark">✓</span>}
            </button>
          ))}
        </div>
      )}

      {isOpen && (
        <div
          className="server-dropdown-overlay"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
}
