import { useState, useEffect } from 'react';
import { healthAPI } from '../api/client';

export default function WakeUpBanner() {
  const [showBanner, setShowBanner] = useState(false);
  const [backendUp, setBackendUp] = useState(false);

  useEffect(() => {
    let graceTimer;
    let pollTimer;
    let cancelled = false;

    const checkHealth = async () => {
      try {
        await healthAPI.check();
        if (!cancelled) setBackendUp(true);
      } catch {
        // still down
      }
    };

    // Initial check
    checkHealth();

    // Show banner only after 2s grace period
    graceTimer = setTimeout(() => {
      if (!cancelled) setShowBanner(true);
    }, 2000);

    // Poll every 3s
    pollTimer = setInterval(checkHealth, 3000);

    return () => {
      cancelled = true;
      clearTimeout(graceTimer);
      clearInterval(pollTimer);
    };
  }, []);

  if (backendUp || !showBanner) return null;

  return (
    <div className="wakeup-banner">
      <div className="wakeup-content">
        <span className="wakeup-spinner" />
        <span>Backend is waking up, this may take a few minutes...</span>
      </div>
    </div>
  );
}
