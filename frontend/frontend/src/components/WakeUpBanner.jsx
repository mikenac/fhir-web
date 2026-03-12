import { useQuery } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import { healthAPI } from '../api/client';

export default function WakeUpBanner() {
  const [dismissed, setDismissed] = useState(false);

  const { isSuccess, isError, isPending } = useQuery({
    queryKey: ['backend-wake-up'],
    queryFn: () => healthAPI.check(),
    retry: 10,
    retryDelay: 3000,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (isSuccess) {
      setDismissed(true);
    }
  }, [isSuccess]);

  if (dismissed || isSuccess) return null;
  if (!isPending && !isError) return null;

  return (
    <div className="wakeup-banner">
      <div className="wakeup-content">
        <span className="wakeup-spinner" />
        <span>Backend is waking up, this may take up to 30 seconds...</span>
      </div>
    </div>
  );
}
