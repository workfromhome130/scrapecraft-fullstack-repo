import React from 'react';
import { usePipelineStore } from '../../store/pipelineStore';
import LoadingSpinner from '../Common/LoadingSpinner';

const OutputView: React.FC = () => {
  const { currentPipeline, executionResults } = usePipelineStore();

  if (!currentPipeline) {
    return (
      <div className="h-full flex items-center justify-center text-muted">
        <p>No pipeline selected</p>
      </div>
    );
  }

  if (currentPipeline.status === 'running') {
    return (
      <div className="h-full flex flex-col items-center justify-center">
        <LoadingSpinner />
        <p className="mt-4 text-muted">Executing pipeline...</p>
      </div>
    );
  }

  if (!executionResults || executionResults.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-muted">
        <p className="text-lg mb-2">No execution results yet</p>
        <p className="text-sm">Click "Run Pipeline" to execute your scraping code</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col p-4">
      <div className="mb-4">
        <h3 className="text-lg font-semibold mb-2">Execution Results</h3>
        <div className="text-sm text-muted">
          Status: <span className={`font-medium ${
            currentPipeline.status === 'completed' ? 'text-success' : 
            currentPipeline.status === 'failed' ? 'text-error' : 
            'text-muted'
          }`}>
            {currentPipeline.status}
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4">
        {executionResults.map((result, index) => (
          <div key={index} className="card">
            <div className="flex items-start justify-between mb-2">
              <h4 className="font-medium">
                Result {index + 1}
                {result.url && <span className="text-sm text-muted ml-2">({result.url})</span>}
              </h4>
              {result.success !== undefined && (
                <span className={`text-sm ${result.success ? 'text-success' : 'text-error'}`}>
                  {result.success ? '✓ Success' : '✗ Failed'}
                </span>
              )}
            </div>
            
            <div className="bg-code-bg rounded-md p-3 overflow-x-auto">
              <pre className="text-sm text-code-text">
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          </div>
        ))}
      </div>

      {executionResults.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border">
          <div className="flex justify-between items-center">
            <span className="text-sm text-muted">
              Total results: {executionResults.length}
            </span>
            <button
              onClick={() => {
                const dataStr = JSON.stringify(executionResults, null, 2);
                const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
                
                const exportFileDefaultName = `scrape_results_${Date.now()}.json`;
                
                const linkElement = document.createElement('a');
                linkElement.setAttribute('href', dataUri);
                linkElement.setAttribute('download', exportFileDefaultName);
                linkElement.click();
              }}
              className="text-sm text-accent hover:underline"
            >
              Export as JSON
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default OutputView;