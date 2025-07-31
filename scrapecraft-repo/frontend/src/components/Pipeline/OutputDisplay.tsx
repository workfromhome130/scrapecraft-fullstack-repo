import React, { useState } from 'react';
import { usePipelineStore } from '../../store/pipelineStore';
import Button from '../Common/Button';

type ViewMode = 'table' | 'json';

const OutputDisplay: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const { currentPipeline, executionResults } = usePipelineStore();

  const renderTableView = () => {
    if (!executionResults || executionResults.length === 0) return null;

    // Get all unique keys from results
    const allKeys = new Set<string>();
    executionResults.forEach(result => {
      if (result.success && result.data) {
        Object.keys(result.data).forEach(key => allKeys.add(key));
      }
    });

    const keys = Array.from(allKeys);

    return (
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border">
              <th className="p-2 text-left text-sm font-medium text-muted">URL</th>
              {keys.map(key => (
                <th key={key} className="p-2 text-left text-sm font-medium text-muted">
                  {key}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {executionResults.map((result, index) => (
              <tr key={index} className="border-b border-border hover:bg-secondary/50">
                <td className="p-2 text-sm">
                  <a
                    href={result.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent hover:underline"
                  >
                    {new URL(result.url).hostname}
                  </a>
                </td>
                {result.success ? (
                  keys.map(key => (
                    <td key={key} className="p-2 text-sm">
                      {result.data[key] || '-'}
                    </td>
                  ))
                ) : (
                  <td colSpan={keys.length} className="p-2 text-sm text-error">
                    Error: {result.error}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const renderJsonView = () => {
    return (
      <pre className="language-json overflow-auto">
        <code>
          {JSON.stringify(executionResults, null, 2)}
        </code>
      </pre>
    );
  };

  const handleExport = (format: 'json' | 'csv') => {
    if (!executionResults || executionResults.length === 0) return;

    let content: string;
    let mimeType: string;
    let extension: string;

    if (format === 'json') {
      content = JSON.stringify(executionResults, null, 2);
      mimeType = 'application/json';
      extension = 'json';
    } else {
      // CSV export
      const successful = executionResults.filter(r => r.success);
      if (successful.length === 0) return;

      const keys = Object.keys(successful[0].data);
      const csv = [
        ['URL', ...keys].join(','),
        ...successful.map(r =>
          [r.url, ...keys.map(k => JSON.stringify(r.data[k] || ''))].join(',')
        )
      ].join('\n');

      content = csv;
      mimeType = 'text/csv';
      extension = 'csv';
    }

    const blob = new Blob([content], { type: mimeType });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentPipeline?.name.replace(/\s+/g, '_')}_results.${extension}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  if (!executionResults || executionResults.length === 0) {
    return (
      <div className="h-full flex items-center justify-center p-4">
        <div className="text-center text-muted">
          <p className="text-lg mb-2">No results yet</p>
          <p className="text-sm">
            Execute your pipeline to see the scraped data here
          </p>
        </div>
      </div>
    );
  }

  const successCount = executionResults.filter(r => r.success).length;
  const failureCount = executionResults.filter(r => !r.success).length;

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center space-x-4">
          <h3 className="text-lg font-semibold">Results</h3>
          <div className="text-sm text-muted">
            <span className="text-success">{successCount} successful</span>
            {failureCount > 0 && (
              <span className="text-error ml-2">{failureCount} failed</span>
            )}
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          <div className="flex rounded-md overflow-hidden">
            <button
              onClick={() => setViewMode('table')}
              className={`px-3 py-1 text-sm ${
                viewMode === 'table'
                  ? 'bg-primary text-white'
                  : 'bg-secondary text-foreground'
              }`}
            >
              Table
            </button>
            <button
              onClick={() => setViewMode('json')}
              className={`px-3 py-1 text-sm ${
                viewMode === 'json'
                  ? 'bg-primary text-white'
                  : 'bg-secondary text-foreground'
              }`}
            >
              JSON
            </button>
          </div>
          
          <Button variant="secondary" size="sm" onClick={() => handleExport('json')}>
            Export JSON
          </Button>
          <Button variant="secondary" size="sm" onClick={() => handleExport('csv')}>
            Export CSV
          </Button>
        </div>
      </div>
      
      <div className="flex-1 overflow-auto p-4">
        {viewMode === 'table' ? renderTableView() : renderJsonView()}
      </div>
    </div>
  );
};

export default OutputDisplay;