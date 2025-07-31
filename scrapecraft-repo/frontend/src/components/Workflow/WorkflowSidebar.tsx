import React, { useEffect, useState } from 'react';
import { useWebSocketStore } from '../../store/websocketStore';
import { usePipelineStore } from '../../store/pipelineStore';
import clsx from 'clsx';

interface WorkflowPhase {
  id: string;
  label: string;
  description: string;
  icon: string;
  status: 'pending' | 'active' | 'completed' | 'error';
}

interface WorkflowState {
  pipeline_id: string;
  phase: string;
  urls: any[];
  schema_fields: any[];
  generated_code: string;
  pending_approvals: any[];
  phase_transitions: any[];
  updated_at: string;
}

const WorkflowSidebar: React.FC = () => {
  const { currentPipeline } = usePipelineStore();
  const { ws, send } = useWebSocketStore();
  const [workflowState, setWorkflowState] = useState<WorkflowState | null>(null);

  const phases: WorkflowPhase[] = [
    {
      id: 'initial',
      label: 'Start',
      description: 'Initialize pipeline',
      icon: '🚀',
      status: 'pending'
    },
    {
      id: 'url_collection',
      label: 'Collect URLs',
      description: 'Find or add URLs to scrape',
      icon: '🔍',
      status: 'pending'
    },
    {
      id: 'url_validation',
      label: 'Validate URLs',
      description: 'Check URL relevance',
      icon: '✅',
      status: 'pending'
    },
    {
      id: 'schema_definition',
      label: 'Define Schema',
      description: 'Specify data to extract',
      icon: '📋',
      status: 'pending'
    },
    {
      id: 'schema_validation',
      label: 'Validate Schema',
      description: 'Verify schema completeness',
      icon: '🔍',
      status: 'pending'
    },
    {
      id: 'code_generation',
      label: 'Generate Code',
      description: 'Create scraping script',
      icon: '💻',
      status: 'pending'
    },
    {
      id: 'ready_to_execute',
      label: 'Ready',
      description: 'Review and approve',
      icon: '👀',
      status: 'pending'
    },
    {
      id: 'executing',
      label: 'Execute',
      description: 'Run the pipeline',
      icon: '▶️',
      status: 'pending'
    },
    {
      id: 'completed',
      label: 'Complete',
      description: 'Pipeline finished',
      icon: '✨',
      status: 'pending'
    }
  ];

  useEffect(() => {
    if (currentPipeline && ws) {
      // Request current workflow state
      send({
        type: 'state_request'
      });
    }
  }, [currentPipeline, ws, send]);

  useEffect(() => {
    // Listen for workflow updates
    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'workflow_state') {
          setWorkflowState(data.workflow);
        } else if (data.type === 'workflow_update') {
          setWorkflowState(data.workflow);
        } else if (data.type === 'approval_request') {
          // Handle approval request
          handleApprovalRequest(data.approval);
        }
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };
    
    // Listen for websocket errors
    const handleError = (event: CustomEvent) => {
      console.log('WebSocket error:', event.detail.message);
    };

    if (ws) {
      ws.addEventListener('message', handleMessage);
      window.addEventListener('websocket-error' as any, handleError);
      
      return () => {
        ws.removeEventListener('message', handleMessage);
        window.removeEventListener('websocket-error' as any, handleError);
      };
    }
  }, [ws]);

  const handleApprovalRequest = (approval: any) => {
    // Show approval dialog or notification
    const approved = window.confirm(`Approval needed: ${approval.action}\n\nApprove this action?`);
    
    send({
      type: 'approval',
      approval_id: approval.id,
      approved: approved
    });
  };

  const getPhaseStatus = (phaseId: string): WorkflowPhase['status'] => {
    if (!workflowState) return 'pending';
    
    const phaseOrder = phases.map(p => p.id);
    const currentIndex = phaseOrder.indexOf(workflowState.phase);
    const targetIndex = phaseOrder.indexOf(phaseId);
    
    if (workflowState.phase === 'error') return 'error';
    if (targetIndex < currentIndex) return 'completed';
    if (targetIndex === currentIndex) return 'active';
    return 'pending';
  };

  const handlePhaseClick = (phaseId: string) => {
    // TODO: Implement manual phase transition
    console.log('Phase clicked:', phaseId);
  };

  return (
    <div className="w-64 bg-secondary p-4 border-r border-border overflow-y-auto">
      <h3 className="text-lg font-semibold mb-4">Workflow Progress</h3>
      
      <div className="space-y-2">
        {phases.map((phase, index) => {
          const status = getPhaseStatus(phase.id);
          const isActive = status === 'active';
          const isCompleted = status === 'completed';
          const isError = status === 'error';
          
          return (
            <div key={phase.id}>
              <div
                className={clsx(
                  'p-3 rounded-lg cursor-pointer transition-all',
                  'hover:bg-background/50',
                  {
                    'bg-primary/20 border border-primary': isActive,
                    'bg-success/10': isCompleted,
                    'bg-error/10': isError,
                    'opacity-50': status === 'pending'
                  }
                )}
                onClick={() => handlePhaseClick(phase.id)}
              >
                <div className="flex items-center space-x-3">
                  <div className={clsx(
                    'text-2xl',
                    isActive && 'animate-pulse'
                  )}>
                    {phase.icon}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium">{phase.label}</div>
                    <div className="text-xs text-muted">{phase.description}</div>
                  </div>
                  {isCompleted && (
                    <div className="text-success">✓</div>
                  )}
                  {isError && (
                    <div className="text-error">✗</div>
                  )}
                </div>
              </div>
              
              {index < phases.length - 1 && (
                <div className={clsx(
                  'w-0.5 h-4 mx-6 transition-colors',
                  isCompleted ? 'bg-success' : 'bg-border'
                )} />
              )}
            </div>
          );
        })}
      </div>
      
      {workflowState ? (
        <div className="mt-6 space-y-4">
          <div className="border-t border-border pt-4">
            <h4 className="font-medium mb-2">Current State</h4>
            <div className="space-y-2 text-sm">
              <div>
                <span className="text-muted">URLs:</span>{' '}
                <span className="font-medium">{workflowState.urls.length}</span>
              </div>
              <div>
                <span className="text-muted">Schema Fields:</span>{' '}
                <span className="font-medium">{workflowState.schema_fields.length}</span>
              </div>
              <div>
                <span className="text-muted">Code:</span>{' '}
                <span className="font-medium">
                  {workflowState.generated_code ? 'Generated' : 'Not ready'}
                </span>
              </div>
            </div>
          </div>
          
          {workflowState.pending_approvals.length > 0 && (
            <div className="border-t border-border pt-4">
              <h4 className="font-medium mb-2 text-warning">
                Pending Approvals ({workflowState.pending_approvals.length})
              </h4>
              <div className="space-y-2">
                {workflowState.pending_approvals.map((approval: any) => (
                  <div
                    key={approval.id}
                    className="p-2 bg-warning/10 rounded text-sm cursor-pointer hover:bg-warning/20"
                    onClick={() => handleApprovalRequest(approval)}
                  >
                    {approval.action}
                  </div>
                ))}
              </div>
            </div>
          )}
          
          <div className="border-t border-border pt-4 text-xs text-muted">
            Last updated: {new Date(workflowState.updated_at).toLocaleTimeString()}
          </div>
        </div>
      ) : (
        <div className="mt-6 text-sm text-muted text-center">
          <p>Start a conversation to begin the workflow</p>
        </div>
      )}
    </div>
  );
};

export default WorkflowSidebar;