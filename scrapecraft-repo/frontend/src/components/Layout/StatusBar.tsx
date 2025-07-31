import React from 'react';
import { usePipelineStore } from '../../store/pipelineStore';
import { useWebSocketStore } from '../../store/websocketStore';

const StatusBar: React.FC = () => {
  const { currentPipeline } = usePipelineStore();
  const { connectionStatus } = useWebSocketStore();

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected':
        return 'text-success';
      case 'connecting':
        return 'text-warning';
      case 'disconnected':
        return 'text-error';
      default:
        return 'text-muted';
    }
  };

  return (
    <div className="bg-secondary border-t border-border px-6 py-2 flex items-center justify-between text-sm">
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-2">
          <span className="text-muted">Status:</span>
          <span className={getStatusColor(currentPipeline?.status || 'idle')}>
            {currentPipeline?.status || 'Idle'}
          </span>
        </div>
        
        <div className="flex items-center space-x-2">
          <span className="text-muted">URLs:</span>
          <span>{currentPipeline?.urls.length || 0}</span>
        </div>
        
        <div className="flex items-center space-x-2">
          <span className="text-muted">Schema Fields:</span>
          <span>{Object.keys(currentPipeline?.schema || {}).length}</span>
        </div>
      </div>
      
      <div className="flex items-center space-x-4 text-xs text-muted">
        <span>ScrapeCraft made by ScrapeGraphAI</span>
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${connectionStatus === 'connected' ? 'bg-success' : 'bg-error'}`} />
          <span className={getStatusColor(connectionStatus)}>
            {connectionStatus}
          </span>
        </div>
      </div>
    </div>
  );
};

export default StatusBar;