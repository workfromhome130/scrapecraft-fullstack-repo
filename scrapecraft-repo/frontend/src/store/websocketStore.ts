import { create } from 'zustand';
import { usePipelineStore } from './pipelineStore';
import { useChatStore } from './chatStore';

interface WebSocketState {
  ws: WebSocket | null;
  connectionStatus: 'connecting' | 'connected' | 'disconnected';
  reconnectAttempts: number;
  
  // Actions
  connect: (pipelineId: string) => void;
  disconnect: () => void;
  send: (data: any) => void;
}

export const useWebSocketStore = create<WebSocketState>((set, get) => ({
  ws: null,
  connectionStatus: 'disconnected',
  reconnectAttempts: 0,

  connect: (pipelineId) => {
    const { ws, disconnect } = get();
    
    // Disconnect existing connection
    if (ws) {
      disconnect();
    }

    set({ connectionStatus: 'connecting' });

    const wsUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:8000';
    const websocket = new WebSocket(`${wsUrl}/ws/${pipelineId}`);

    websocket.onopen = () => {
      console.log('WebSocket connected');
      set({ 
        ws: websocket, 
        connectionStatus: 'connected',
        reconnectAttempts: 0 
      });
    };

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    websocket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    websocket.onclose = () => {
      console.log('WebSocket disconnected');
      set({ connectionStatus: 'disconnected' });
      
      // Attempt to reconnect
      const { reconnectAttempts } = get();
      if (reconnectAttempts < 5) {
        setTimeout(() => {
          set((state) => ({ reconnectAttempts: state.reconnectAttempts + 1 }));
          get().connect(pipelineId);
        }, Math.min(1000 * Math.pow(2, reconnectAttempts), 10000));
      }
    };
  },

  disconnect: () => {
    const { ws } = get();
    if (ws) {
      ws.close();
      set({ ws: null, connectionStatus: 'disconnected' });
    }
  },

  send: (data) => {
    const { ws, connectionStatus } = get();
    if (ws && connectionStatus === 'connected') {
      ws.send(JSON.stringify(data));
    }
  }
}));

// Handle incoming WebSocket messages
function handleWebSocketMessage(data: any) {
  const { type } = data;
  
  switch (type) {
    case 'state_update':
      // Update pipeline state
      if (data.state) {
        const pipelineStore = usePipelineStore.getState();
        const currentPipeline = pipelineStore.currentPipeline;
        if (currentPipeline) {
          pipelineStore.updatePipeline(currentPipeline.id, data.state);
        }
      }
      break;
      
    case 'workflow_update':
      // Update workflow state
      if (data.workflow) {
        const { useWorkflowStore } = require('./workflowStore');
        const workflowStore = useWorkflowStore.getState();
        workflowStore.setWorkflow(data.workflow);
      }
      break;
      
    case 'workflow_state':
      // Set initial workflow state
      if (data.workflow) {
        const { useWorkflowStore } = require('./workflowStore');
        const workflowStore = useWorkflowStore.getState();
        workflowStore.setWorkflow(data.workflow);
      }
      // Notify that state was received (even if null)
      window.dispatchEvent(new CustomEvent('workflow-state-received'));
      break;
      
    case 'approval_request':
      // Handle approval requests
      if (data.approval) {
        const { useWorkflowStore } = require('./workflowStore');
        const workflowStore = useWorkflowStore.getState();
        // Trigger UI to show approval dialog
        window.dispatchEvent(new CustomEvent('approval-request', { detail: data.approval }));
      }
      break;
      
    case 'execution_update':
      // Handle execution updates
      console.log('Execution update:', data);
      break;
      
    case 'error':
      // Handle error messages
      console.error('WebSocket error:', data.message);
      // Notify components about the error
      window.dispatchEvent(new CustomEvent('websocket-error', { detail: data }));
      break;
      
    case 'response':
      // Handle AI responses
      if (data.response) {
        const chatStore = useChatStore.getState();
        chatStore.addMessage({
          id: Date.now().toString(),
          role: 'assistant',
          content: data.response,
          timestamp: new Date().toISOString()
        });
      }
      
      // Also update workflow if included
      if (data.workflow_state) {
        const { useWorkflowStore } = require('./workflowStore');
        const workflowStore = useWorkflowStore.getState();
        workflowStore.setWorkflow(data.workflow_state);
      }
      break;
      
    default:
      console.log('Unknown WebSocket message type:', type);
  }
}