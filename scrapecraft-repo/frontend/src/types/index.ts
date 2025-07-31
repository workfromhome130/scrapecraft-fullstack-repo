// Chat Types
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  metadata?: {
    toolsUsed?: string[];
    executionTime?: number;
  };
}

// Pipeline Types
export interface Pipeline {
  id: string;
  name: string;
  description?: string;
  urls: string[];
  schema: Record<string, any>;
  code: string;
  generated_code?: string;
  status: 'idle' | 'running' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  results?: any[];
  results_count?: number;
  last_run?: string;
}

export interface PipelineCreate {
  name: string;
  description?: string;
  urls?: string[];
  schema?: Record<string, any>;
}

export interface PipelineUpdate {
  name?: string;
  description?: string;
  urls?: string[];
  schema?: Record<string, any>;
  code?: string;
}

// WebSocket Event Types
export interface WSEvents {
  'chat:message': {
    content: string;
    pipelineId: string;
  };
  'pipeline:update': {
    pipelineId: string;
    updates: Partial<Pipeline>;
  };
  'execution:start': {
    pipelineId: string;
  };
  'execution:progress': {
    pipelineId: string;
    current: number;
    total: number;
    url: string;
  };
  'execution:complete': {
    pipelineId: string;
    results: any[];
  };
  'execution:error': {
    pipelineId: string;
    error: string;
  };
}

// Scraping Result Types
export interface ScrapingResult {
  url: string;
  success: boolean;
  data: Record<string, any>;
  error?: string;
}

// User Types
export interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string;
}