import { useQuery } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import { healthAPI } from '../api/client';

export default function WakeUpBanner() {
  const [showBanner, setShowBanner] = useState(false);

  const { isSuccess } = useQuery({
    queryKey: ['backend-wake-up'],
    queryFn: () => healthAPI.check(),
    retry: 100,
    retryDelay: 3000,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  // Only show the banner if the backend hasn't responded within 2 seconds.
  // This prevents a flash on fast connections where the health check succeeds immediately.
  useEffect(() => {
    if (isSuccess) return;
    const timer = setTimeout(() => setShowBanner(true), 2000);
    return () => clearTimeout(timer);
  }, [isSuccess]);

  if (isSuccess || !showBanner) return null;

  return (
    <div className="wakeup-banner">
      <div className="wakeup-content">
        <span className="wakeup-spinner" />
        <span>Backend is waking up, this may take up to 30 seconds...</span>
      </div>
    </div>
  );
}
