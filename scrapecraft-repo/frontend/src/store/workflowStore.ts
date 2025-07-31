import { create } from 'zustand';
import { api } from '../services/api';

export enum WorkflowPhase {
  INITIAL = 'initial',
  URL_COLLECTION = 'url_collection',
  URL_VALIDATION = 'url_validation',
  SCHEMA_DEFINITION = 'schema_definition',
  SCHEMA_VALIDATION = 'schema_validation',
  CODE_GENERATION = 'code_generation',
  READY_TO_EXECUTE = 'ready_to_execute',
  EXECUTING = 'executing',
  COMPLETED = 'completed',
  ERROR = 'error'
}

interface URLInfo {
  url: string;
  description: string;
  relevance: 'high' | 'medium' | 'low';
  validated: boolean;
  validation_reason?: string;
  added_at: string;
  added_by: string;
}

interface SchemaField {
  name: string;
  type: string;
  description: string;
  required: boolean;
  example?: string;
}

interface ApprovalRequest {
  id: string;
  phase: WorkflowPhase;
  action: string;
  data: any;
  created_at: string;
  expires_at?: string;
  status: 'pending' | 'approved' | 'rejected' | 'expired';
}

interface WorkflowTransition {
  from_phase: WorkflowPhase;
  to_phase: WorkflowPhase;
  timestamp: string;
  reason?: string;
  triggered_by: string;
}

interface WorkflowState {
  pipeline_id: string;
  phase: WorkflowPhase;
  urls: URLInfo[];
  urls_validated: boolean;
  schema_fields: SchemaField[];
  schema_validated: boolean;
  generated_code: string;
  code_validated: boolean;
  execution_results: any[];
  execution_status?: string;
  pending_approvals: ApprovalRequest[];
  approval_history: ApprovalRequest[];
  phase_transitions: WorkflowTransition[];
  user_modifications: any[];
  created_at: string;
  updated_at: string;
  created_by: string;
  last_modified_by: string;
  version: number;
}

interface WorkflowStore {
  // State
  currentWorkflow: WorkflowState | null;
  workflowHistory: WorkflowTransition[];
  pendingApprovals: ApprovalRequest[];
  isProcessing: boolean;
  error: string | null;

  // Actions
  setWorkflow: (workflow: WorkflowState) => void;
  updateWorkflowPhase: (phase: WorkflowPhase) => void;
  addURLs: (urls: URLInfo[]) => void;
  updateURLs: (urls: URLInfo[]) => Promise<void>;
  updateSchema: (fields: SchemaField[]) => Promise<void>;
  approveAction: (approvalId: string, approved: boolean, reason?: string) => Promise<void>;
  transitionToPhase: (phase: WorkflowPhase, reason?: string) => Promise<void>;
  fetchWorkflow: (pipelineId: string) => Promise<void>;
  fetchWorkflowHistory: (pipelineId: string) => Promise<void>;
  clearError: () => void;
}

export const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  // Initial state
  currentWorkflow: null,
  workflowHistory: [],
  pendingApprovals: [],
  isProcessing: false,
  error: null,

  // Actions
  setWorkflow: (workflow) => {
    set({
      currentWorkflow: workflow,
      pendingApprovals: workflow.pending_approvals,
      workflowHistory: workflow.phase_transitions
    });
  },

  updateWorkflowPhase: (phase) => {
    set((state) => ({
      currentWorkflow: state.currentWorkflow
        ? { ...state.currentWorkflow, phase }
        : null
    }));
  },

  addURLs: (urls) => {
    set((state) => ({
      currentWorkflow: state.currentWorkflow
        ? {
            ...state.currentWorkflow,
            urls: [...state.currentWorkflow.urls, ...urls]
          }
        : null
    }));
  },

  updateURLs: async (urls) => {
    const { currentWorkflow } = get();
    if (!currentWorkflow) return;

    set({ isProcessing: true, error: null });

    try {
      const response = await api.post(`/workflow/${currentWorkflow.pipeline_id}/urls`, urls);
      set({ currentWorkflow: response.data.workflow });
    } catch (error: any) {
      set({ error: error.response?.data?.detail || 'Failed to update URLs' });
    } finally {
      set({ isProcessing: false });
    }
  },

  updateSchema: async (fields) => {
    const { currentWorkflow } = get();
    if (!currentWorkflow) return;

    set({ isProcessing: true, error: null });

    try {
      const response = await api.post(`/workflow/${currentWorkflow.pipeline_id}/schema`, fields);
      set({ currentWorkflow: response.data.workflow });
    } catch (error: any) {
      set({ error: error.response?.data?.detail || 'Failed to update schema' });
    } finally {
      set({ isProcessing: false });
    }
  },

  approveAction: async (approvalId, approved, reason) => {
    const { currentWorkflow } = get();
    if (!currentWorkflow) return;

    set({ isProcessing: true, error: null });

    try {
      const response = await api.post(`/workflow/${currentWorkflow.pipeline_id}/approve`, {
        approval_id: approvalId,
        approved,
        reason
      });
      
      set({
        currentWorkflow: response.data.workflow,
        pendingApprovals: response.data.workflow.pending_approvals
      });
    } catch (error: any) {
      set({ error: error.response?.data?.detail || 'Failed to process approval' });
    } finally {
      set({ isProcessing: false });
    }
  },

  transitionToPhase: async (phase, reason) => {
    const { currentWorkflow } = get();
    if (!currentWorkflow) return;

    set({ isProcessing: true, error: null });

    try {
      const response = await api.post(`/workflow/${currentWorkflow.pipeline_id}/transition`, {
        target_phase: phase,
        reason
      });
      
      set({ currentWorkflow: response.data.workflow });
    } catch (error: any) {
      set({ error: error.response?.data?.detail || 'Failed to transition phase' });
    } finally {
      set({ isProcessing: false });
    }
  },

  fetchWorkflow: async (pipelineId) => {
    set({ isProcessing: true, error: null });

    try {
      const response = await api.get(`/workflow/${pipelineId}`);
      set({ currentWorkflow: response.data });
    } catch (error: any) {
      set({ error: error.response?.data?.detail || 'Failed to fetch workflow' });
    } finally {
      set({ isProcessing: false });
    }
  },

  fetchWorkflowHistory: async (pipelineId) => {
    try {
      const response = await api.get(`/workflow/${pipelineId}/history`);
      set({ workflowHistory: response.data.transitions });
    } catch (error: any) {
      console.error('Failed to fetch workflow history:', error);
    }
  },

  clearError: () => {
    set({ error: null });
  }
}));