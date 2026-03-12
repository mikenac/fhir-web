import { useState, useEffect, useRef } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function WakeUpBanner() {
  const [showBanner, setShowBanner] = useState(false);
  const [backendUp, setBackendUp] = useState(false);
  const inFlight = useRef(false);

  useEffect(() => {
    let graceTimer;
    let pollTimer;
    let cancelled = false;

    const checkHealth = async () => {
      // Skip if a request is already in flight
      if (inFlight.current) return;
      inFlight.current = true;

      try {
        // Use raw fetch with a timeout instead of axios to bypass
        // the error interceptor which may interfere with retries
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);

        const res = await fetch(`${API_BASE_URL}/health`, {
          signal: controller.signal,
        });
        clearTimeout(timeout);

        if (res.ok && !cancelled) {
          console.log('[WakeUpBanner] Backend is up');
          setBackendUp(true);
          clearInterval(pollTimer);
        }
      } catch {
        // still down or timed out
      } finally {
        inFlight.current = false;
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
