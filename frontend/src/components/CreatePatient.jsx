import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { patientAPI } from '../api/client';

function CreatePatient() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    family_name: '',
    given_names: [''],
    birth_date: '',
    mrn: '',
    mrn_system: 'http://hospital.example.org/mrn',
    gender: '',
    phone: '',
    email: '',
  });

  const mutation = useMutation({
    mutationFn: (data) => patientAPI.create(data),
    onSuccess: (response) => {
      navigate(`/patients/${response.data.id}`);
    },
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    if (name === 'given_names') {
      setFormData({ ...formData, given_names: [value] });
    } else {
      setFormData({ ...formData, [name]: value });
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    mutation.mutate(formData);
  };

  return (
    <div className="create-patient">
      <h2>Create New Patient</h2>

      <form onSubmit={handleSubmit} className="patient-form">
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="given_names">First Name *</label>
            <input
              type="text"
              id="given_names"
              name="given_names"
              value={formData.given_names[0]}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="family_name">Last Name *</label>
            <input
              type="text"
              id="family_name"
              name="family_name"
              value={formData.family_name}
              onChange={handleChange}
              required
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="birth_date">Birth Date *</label>
            <input
              type="date"
              id="birth_date"
              name="birth_date"
              value={formData.birth_date}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="gender">Gender</label>
            <select id="gender" name="gender" value={formData.gender} onChange={handleChange}>
              <option value="">Select...</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="mrn">Medical Record Number (MRN) *</label>
            <input
              type="text"
              id="mrn"
              name="mrn"
              value={formData.mrn}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="mrn_system">MRN System</label>
            <input
              type="text"
              id="mrn_system"
              name="mrn_system"
              value={formData.mrn_system}
              onChange={handleChange}
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="phone">Phone</label>
            <input
              type="tel"
              id="phone"
              name="phone"
              value={formData.phone}
              onChange={handleChange}
            />
          </div>

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
            />
          </div>
        </div>

        {mutation.isError && <div className="error">Error: {mutation.error.message}</div>}

        <div className="form-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate('/patients/search')}
          >
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={mutation.isPending}>
            {mutation.isPending ? 'Creating...' : 'Create Patient'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default CreatePatient;
