import React, { useState } from 'react';
import Button from '../Common/Button';
import clsx from 'clsx';

interface ApprovalDialogProps {
  approval: {
    id: string;
    phase: string;
    action: string;
    data: any;
  };
  onApprove: (approvalId: string, reason?: string) => void;
  onReject: (approvalId: string, reason?: string) => void;
  onClose: () => void;
}

const ApprovalDialog: React.FC<ApprovalDialogProps> = ({
  approval,
  onApprove,
  onReject,
  onClose
}) => {
  const [reason, setReason] = useState('');
  const [showReason, setShowReason] = useState(false);

  const handleApprove = () => {
    onApprove(approval.id, reason);
    onClose();
  };

  const handleReject = () => {
    if (!showReason) {
      setShowReason(true);
      return;
    }
    onReject(approval.id, reason);
    onClose();
  };

  const renderApprovalContent = () => {
    switch (approval.action) {
      case 'validate_urls':
        return (
          <div className="space-y-4">
            <p className="text-sm text-muted">
              The agent has found and validated URLs. Please review:
            </p>
            <div className="max-h-60 overflow-y-auto space-y-2">
              {approval.data.urls?.map((url: any, index: number) => (
                <div key={index} className="p-3 bg-secondary rounded-lg">
                  <div className="font-medium text-sm">{url.url}</div>
                  {url.description && (
                    <div className="text-xs text-muted mt-1">{url.description}</div>
                  )}
                  <div className="flex items-center mt-2 space-x-4 text-xs">
                    <span className={clsx(
                      'px-2 py-1 rounded',
                      url.relevance === 'high' ? 'bg-success/20 text-success' :
                      url.relevance === 'medium' ? 'bg-warning/20 text-warning' :
                      'bg-muted/20 text-muted'
                    )}>
                      {url.relevance} relevance
                    </span>
                    {url.validated && (
                      <span className="text-success">✓ Validated</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case 'approve_schema':
        return (
          <div className="space-y-4">
            <p className="text-sm text-muted">
              Review the data extraction schema:
            </p>
            <div className="max-h-60 overflow-y-auto space-y-2">
              {approval.data.schema_fields?.map((field: any, index: number) => (
                <div key={index} className="p-3 bg-secondary rounded-lg">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{field.name}</span>
                    <span className="text-xs text-accent">{field.type}</span>
                  </div>
                  {field.description && (
                    <div className="text-xs text-muted mt-1">{field.description}</div>
                  )}
                  {field.example && (
                    <div className="text-xs text-muted mt-1">
                      Example: {field.example}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        );

      case 'execute_code':
        return (
          <div className="space-y-4">
            <p className="text-sm text-muted">
              Ready to execute the generated code. This will:
            </p>
            <ul className="list-disc list-inside text-sm space-y-1">
              <li>Run the SmartScraper API on {approval.data.url_count || 0} URLs</li>
              <li>Extract data according to your schema</li>
              <li>Use your configured API key</li>
            </ul>
            <div className="p-3 bg-warning/10 rounded-lg text-sm">
              <p className="font-medium text-warning mb-1">⚠️ Important:</p>
              <p className="text-xs">
                This will consume API credits. Make sure you want to proceed.
              </p>
            </div>
          </div>
        );

      default:
        return (
          <div className="space-y-4">
            <p className="text-sm text-muted">
              Action required: {approval.action}
            </p>
            {approval.data && (
              <pre className="text-xs bg-secondary p-3 rounded overflow-auto max-h-60">
                {JSON.stringify(approval.data, null, 2)}
              </pre>
            )}
          </div>
        );
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background border border-border rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Approval Required</h3>
          <button
            onClick={onClose}
            className="text-muted hover:text-foreground transition-colors"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto mb-4">
          {renderApprovalContent()}
        </div>

        {showReason && (
          <div className="mb-4">
            <label className="block text-sm font-medium mb-2">
              Reason for rejection (optional):
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="input w-full"
              rows={3}
              placeholder="Explain why you're rejecting this..."
              autoFocus
            />
          </div>
        )}

        <div className="flex justify-end space-x-3">
          <Button
            variant="secondary"
            onClick={handleReject}
          >
            {showReason ? 'Confirm Rejection' : 'Reject'}
          </Button>
          <Button
            variant="primary"
            onClick={handleApprove}
          >
            Approve
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ApprovalDialog;