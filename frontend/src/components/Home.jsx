import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { patientAPI, healthAPI } from '../api/client';

function Home() {
  const navigate = useNavigate();
  const [searchType, setSearchType] = useState('name');
  const [searchParams, setSearchParams] = useState({
    familyName: '',
    givenName: '',
    patientId: '',
    mrn: '',
  });
  const [activeSearch, setActiveSearch] = useState(null);

  const { data: healthData } = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await healthAPI.check();
      return response.data;
    },
  });

  const { data: searchResults, isLoading, error } = useQuery({
    queryKey: ['patientSearch', activeSearch],
    queryFn: async () => {
      if (activeSearch.type === 'name') {
        const response = await patientAPI.search(activeSearch.familyName, activeSearch.givenName);
        return response.data;
      } else if (activeSearch.type === 'id') {
        const response = await patientAPI.get(activeSearch.patientId);
        return { total: 1, results: [response.data] };
      } else if (activeSearch.type === 'mrn') {
        const response = await patientAPI.getByMRN(activeSearch.mrn);
        return { total: 1, results: [response.data] };
      }
    },
    enabled: !!activeSearch,
  });

  const handleSearch = (e) => {
    e.preventDefault();

    if (searchType === 'name' && (searchParams.familyName || searchParams.givenName)) {
      setActiveSearch({
        type: 'name',
        familyName: searchParams.familyName,
        givenName: searchParams.givenName,
      });
    } else if (searchType === 'id' && searchParams.patientId.trim()) {
      setActiveSearch({
        type: 'id',
        patientId: searchParams.patientId.trim(),
      });
    } else if (searchType === 'mrn' && searchParams.mrn.trim()) {
      setActiveSearch({
        type: 'mrn',
        mrn: searchParams.mrn.trim(),
      });
    }
  };

  const handlePatientClick = (patientId) => {
    navigate(`/patients/${patientId}`);
  };

  return (
    <div className="home">
      <div className="hero">
        <h1>Find Patients</h1>
        <p>Search for patients by name, ID, or medical record number</p>
        {healthData && (
          <p className="status-badge">
            Server: <span className="status-healthy">{healthData.status}</span>
          </p>
        )}
      </div>

      <div className="search-container">
        <div className="search-type-selector">
          <button
            className={`search-type-btn ${searchType === 'name' ? 'active' : ''}`}
            onClick={() => setSearchType('name')}
          >
            Search by Name
          </button>
          <button
            className={`search-type-btn ${searchType === 'id' ? 'active' : ''}`}
            onClick={() => setSearchType('id')}
          >
            Search by Patient ID
          </button>
          <button
            className={`search-type-btn ${searchType === 'mrn' ? 'active' : ''}`}
            onClick={() => setSearchType('mrn')}
          >
            Search by MRN
          </button>
        </div>

        <form onSubmit={handleSearch} className="search-form">
          {searchType === 'name' && (
            <div className="search-fields">
              <div className="form-group">
                <label htmlFor="familyName">Last Name</label>
                <input
                  type="text"
                  id="familyName"
                  value={searchParams.familyName}
                  onChange={(e) =>
                    setSearchParams({ ...searchParams, familyName: e.target.value })
                  }
                  placeholder="Smith"
                  autoFocus
                />
              </div>
              <div className="form-group">
                <label htmlFor="givenName">First Name</label>
                <input
                  type="text"
                  id="givenName"
                  value={searchParams.givenName}
                  onChange={(e) => setSearchParams({ ...searchParams, givenName: e.target.value })}
                  placeholder="John"
                />
              </div>
            </div>
          )}

          {searchType === 'id' && (
            <div className="search-fields">
              <div className="form-group">
                <label htmlFor="patientId">Patient ID</label>
                <input
                  type="text"
                  id="patientId"
                  value={searchParams.patientId}
                  onChange={(e) => setSearchParams({ ...searchParams, patientId: e.target.value })}
                  placeholder="Enter FHIR patient ID"
                  autoFocus
                />
              </div>
            </div>
          )}

          {searchType === 'mrn' && (
            <div className="search-fields">
              <div className="form-group">
                <label htmlFor="mrn">Medical Record Number</label>
                <input
                  type="text"
                  id="mrn"
                  value={searchParams.mrn}
                  onChange={(e) => setSearchParams({ ...searchParams, mrn: e.target.value })}
                  placeholder="Enter MRN"
                  autoFocus
                />
              </div>
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary btn-large"
            disabled={
              isLoading ||
              (searchType === 'name' && !searchParams.familyName && !searchParams.givenName) ||
              (searchType === 'id' && !searchParams.patientId.trim()) ||
              (searchType === 'mrn' && !searchParams.mrn.trim())
            }
          >
            {isLoading ? 'Searching...' : 'Search Patients'}
          </button>
        </form>
      </div>

      {error && (
        <div className="error-box">
          <h3>Error</h3>
          <p>{error.message}</p>
        </div>
      )}

      {searchResults && (
        <div className="search-results">
          <h3>
            {searchResults.total === 0 ? 'No Patients Found' : `Found ${searchResults.total} Patient${searchResults.total !== 1 ? 's' : ''}`}
          </h3>
          {searchResults.total > 0 && (
            <div className="patient-list">
              {searchResults.results.map((patient) => (
                <div
                  key={patient.id}
                  className="patient-card clickable"
                  onClick={() => handlePatientClick(patient.id)}
                >
                  <div className="patient-header">
                    <h4>{patient.full_name}</h4>
                    <span className="patient-id">ID: {patient.id}</span>
                  </div>
                  <div className="patient-details">
                    <div className="detail-item">
                      <strong>MRN:</strong> <span>{patient.mrn}</span>
                    </div>
                    <div className="detail-item">
                      <strong>Birth Date:</strong> <span>{patient.birth_date}</span>
                    </div>
                    {patient.gender && (
                      <div className="detail-item">
                        <strong>Gender:</strong> <span>{patient.gender}</span>
                      </div>
                    )}
                    {patient.phone && (
                      <div className="detail-item">
                        <strong>Phone:</strong> <span>{patient.phone}</span>
                      </div>
                    )}
                  </div>
                  <div className="patient-footer">
                    <span className="view-details">Click to view details →</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default Home;
