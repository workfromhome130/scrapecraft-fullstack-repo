import { create } from 'zustand';
import { Pipeline, PipelineCreate, PipelineUpdate } from '../types';
import { api } from '../services/api';

interface PipelineState {
  pipelines: Pipeline[];
  currentPipeline: Pipeline | null;
  executionResults: any[];
  isLoading: boolean;
  
  // Actions
  fetchPipelines: () => Promise<void>;
  createPipeline: (data: PipelineCreate) => Promise<void>;
  updatePipeline: (id: string, data: PipelineUpdate) => Promise<void>;
  deletePipeline: (id: string) => Promise<void>;
  setCurrentPipeline: (pipeline: Pipeline | null) => void;
  runPipeline: (id: string) => Promise<void>;
  setExecutionResults: (results: any[]) => void;
}

export const usePipelineStore = create<PipelineState>((set, get) => ({
  pipelines: [],
  currentPipeline: null,
  executionResults: [],
  isLoading: false,

  fetchPipelines: async () => {
    try {
      const response = await api.get('/pipelines');
      set({ pipelines: response.data });
      
      // Set current pipeline if none selected
      const { currentPipeline, pipelines } = get();
      if (!currentPipeline && pipelines.length > 0) {
        set({ currentPipeline: pipelines[0] });
      }
    } catch (error) {
      console.error('Failed to fetch pipelines:', error);
    }
  },

  createPipeline: async (data) => {
    set({ isLoading: true });
    try {
      const response = await api.post('/pipelines', data);
      const newPipeline = response.data;
      
      set((state) => ({
        pipelines: [...state.pipelines, newPipeline],
        currentPipeline: newPipeline,
        isLoading: false
      }));
    } catch (error) {
      console.error('Failed to create pipeline:', error);
      set({ isLoading: false });
    }
  },

  updatePipeline: async (id, data) => {
    try {
      const response = await api.put(`/pipelines/${id}`, data);
      const updatedPipeline = response.data;
      
      set((state) => ({
        pipelines: state.pipelines.map(p => 
          p.id === id ? updatedPipeline : p
        ),
        currentPipeline: state.currentPipeline?.id === id 
          ? updatedPipeline 
          : state.currentPipeline
      }));
    } catch (error) {
      console.error('Failed to update pipeline:', error);
    }
  },

  deletePipeline: async (id) => {
    try {
      await api.delete(`/pipelines/${id}`);
      
      set((state) => {
        const pipelines = state.pipelines.filter(p => p.id !== id);
        const currentPipeline = state.currentPipeline?.id === id 
          ? pipelines[0] || null 
          : state.currentPipeline;
        
        return { pipelines, currentPipeline };
      });
    } catch (error) {
      console.error('Failed to delete pipeline:', error);
    }
  },

  setCurrentPipeline: (pipeline) => {
    set({ currentPipeline: pipeline });
  },

  runPipeline: async (id) => {
    try {
      const { currentPipeline } = get();
      if (!currentPipeline) return;
      
      // Get API key from localStorage (from settings)
      const apiKey = localStorage.getItem('SCRAPEGRAPH_API_KEY');
      
      // Update pipeline status
      set((state) => ({
        pipelines: state.pipelines.map(p => 
          p.id === id ? { ...p, status: 'running' } : p
        ),
        currentPipeline: state.currentPipeline?.id === id 
          ? { ...state.currentPipeline, status: 'running' }
          : state.currentPipeline
      }));
      
      // Execute the pipeline
      const response = await api.post('/execution/execute', {
        pipeline_id: id,
        code: currentPipeline.generated_code || '',
        urls: currentPipeline.urls || [],
        schema: currentPipeline.schema || {},
        api_key: apiKey
      });
      
      // Update with results
      set((state) => ({
        executionResults: response.data.results,
        pipelines: state.pipelines.map(p => 
          p.id === id ? { ...p, status: 'completed', results: response.data.results } : p
        ),
        currentPipeline: state.currentPipeline?.id === id 
          ? { ...state.currentPipeline, status: 'completed', results: response.data.results }
          : state.currentPipeline
      }));
      
    } catch (error) {
      console.error('Failed to run pipeline:', error);
      
      // Update status to failed
      set((state) => ({
        pipelines: state.pipelines.map(p => 
          p.id === id ? { ...p, status: 'failed' } : p
        ),
        currentPipeline: state.currentPipeline?.id === id 
          ? { ...state.currentPipeline, status: 'failed' }
          : state.currentPipeline
      }));
    }
  },

  setExecutionResults: (results) => {
    set({ executionResults: results });
  }
}));