import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import './App.css';
import PatientDetail from './components/PatientDetail';
import Home from './components/Home';
import ServerSelector from './components/ServerSelector';
import WakeUpBanner from './components/WakeUpBanner';
import { FHIRServerProvider } from './contexts/FHIRServerContext';

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
    <FHIRServerProvider>
      <QueryClientProvider client={queryClient}>
        <Router>
          <WakeUpBanner />
          <div className="app">
            <nav className="navbar">
              <div className="nav-brand">
                <Link to="/" style={{ textDecoration: 'none', color: 'inherit' }}>
                  <h1>FHIR Patient Finder</h1>
                </Link>
              </div>
              <ServerSelector />
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
    </FHIRServerProvider>
  );
}

export default App;
