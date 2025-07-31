import { useEffect } from 'react';
import { useWebSocketStore } from '../store/websocketStore';

export const useWebSocket = (pipelineId: string) => {
  const { connect, disconnect } = useWebSocketStore();

  useEffect(() => {
    if (pipelineId) {
      connect(pipelineId);
    }

    return () => {
      disconnect();
    };
  }, [pipelineId, connect, disconnect]);
};