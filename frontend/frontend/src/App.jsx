import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import './App.css';
import PatientDetail from './components/PatientDetail';
import Home from './components/Home';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="app">
          <nav className="navbar">
            <div className="nav-brand">
              <Link to="/" style={{ textDecoration: 'none', color: 'inherit' }}>
                <h1>FHIR Patient Finder</h1>
              </Link>
            </div>
          </nav>

          <main className="main-content">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/patients/:patientId" element={<PatientDetail />} />
            </Routes>
          </main>
        </div>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
