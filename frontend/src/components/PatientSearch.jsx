import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { patientAPI } from '../api/client';

function PatientSearch() {
  const [familyName, setFamilyName] = useState('');
  const [givenName, setGivenName] = useState('');
  const [searchParams, setSearchParams] = useState(null);
  const navigate = useNavigate();

  const { data, isLoading, error } = useQuery({
    queryKey: ['patients', searchParams],
    queryFn: async () => {
      const response = await patientAPI.search(searchParams.family, searchParams.given);
      return response.data;
    },
    enabled: !!searchParams,
  });

  const handleSearch = (e) => {
    e.preventDefault();
    if (familyName || givenName) {
      setSearchParams({ family: familyName, given: givenName });
    }
  };

  const handlePatientClick = (patientId) => {
    navigate(`/patients/${patientId}`);
  };

  return (
    <div className="patient-search">
      <h2>Search Patients</h2>

      <form onSubmit={handleSearch} className="search-form">
        <div className="form-group">
          <label htmlFor="familyName">Family Name (Last Name)</label>
          <input
            type="text"
            id="familyName"
            value={familyName}
            onChange={(e) => setFamilyName(e.target.value)}
            placeholder="e.g., Smith"
          />
        </div>

        <div className="form-group">
          <label htmlFor="givenName">Given Name (First Name)</label>
          <input
            type="text"
            id="givenName"
            value={givenName}
            onChange={(e) => setGivenName(e.target.value)}
            placeholder="e.g., John"
          />
        </div>

        <button type="submit" className="btn btn-primary" disabled={!familyName && !givenName}>
          Search
        </button>
      </form>

      {isLoading && <div className="loading">Searching...</div>}

      {error && <div className="error">Error: {error.message}</div>}

      {data && (
        <div className="search-results">
          <h3>Results ({data.total} found)</h3>
          {data.total === 0 ? (
            <p>No patients found matching your search criteria.</p>
          ) : (
            <div className="patient-list">
              {data.results.map((patient) => (
                <div
                  key={patient.id}
                  className="patient-card"
                  onClick={() => handlePatientClick(patient.id)}
                >
                  <h4>{patient.full_name}</h4>
                  <div className="patient-details">
                    <p>
                      <strong>MRN:</strong> {patient.mrn}
                    </p>
                    <p>
                      <strong>Birth Date:</strong> {patient.birth_date}
                    </p>
                    {patient.gender && (
                      <p>
                        <strong>Gender:</strong> {patient.gender}
                      </p>
                    )}
                    {patient.phone && (
                      <p>
                        <strong>Phone:</strong> {patient.phone}
                      </p>
                    )}
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

export default PatientSearch;
