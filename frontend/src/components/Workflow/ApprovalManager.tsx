import React, { useEffect, useState } from 'react';
import { useWebSocketStore } from '../../store/websocketStore';
import { useWorkflowStore } from '../../store/workflowStore';
import ApprovalDialog from './ApprovalDialog';

const ApprovalManager: React.FC = () => {
  const { send } = useWebSocketStore();
  const { approveAction } = useWorkflowStore();
  const [currentApproval, setCurrentApproval] = useState<any>(null);

  useEffect(() => {
    const handleApprovalRequest = (event: CustomEvent) => {
      setCurrentApproval(event.detail);
    };

    window.addEventListener('approval-request' as any, handleApprovalRequest);
    return () => {
      window.removeEventListener('approval-request' as any, handleApprovalRequest);
    };
  }, []);

  const handleApprove = async (approvalId: string, reason?: string) => {
    // Send via WebSocket for immediate response
    send({
      type: 'approval',
      approval_id: approvalId,
      approved: true,
      reason
    });

    // Also update via API
    await approveAction(approvalId, true, reason);
    setCurrentApproval(null);
  };

  const handleReject = async (approvalId: string, reason?: string) => {
    // Send via WebSocket for immediate response
    send({
      type: 'approval',
      approval_id: approvalId,
      approved: false,
      reason
    });

    // Also update via API
    await approveAction(approvalId, false, reason);
    setCurrentApproval(null);
  };

  const handleClose = () => {
    setCurrentApproval(null);
  };

  if (!currentApproval) {
    return null;
  }

  return (
    <ApprovalDialog
      approval={currentApproval}
      onApprove={handleApprove}
      onReject={handleReject}
      onClose={handleClose}
    />
  );
};

export default ApprovalManager;