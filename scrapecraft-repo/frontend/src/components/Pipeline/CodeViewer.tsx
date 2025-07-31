import React, { useEffect } from 'react';
import { usePipelineStore } from '../../store/pipelineStore';
import Button from '../Common/Button';
import Prism from 'prismjs';

const CodeViewer: React.FC = () => {
  const { currentPipeline } = usePipelineStore();

  useEffect(() => {
    // Highlight code when it changes
    Prism.highlightAll();
  }, [currentPipeline?.code]);

  const handleCopyCode = () => {
    if (currentPipeline?.code) {
      navigator.clipboard.writeText(currentPipeline.code);
      // You could add a toast notification here
    }
  };

  const handleDownloadCode = () => {
    if (currentPipeline?.code) {
      const blob = new Blob([currentPipeline.code], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${currentPipeline.name.replace(/\s+/g, '_')}_scraper.py`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }
  };

  if (!currentPipeline?.code) {
    return (
      <div className="h-full flex items-center justify-center p-4">
        <div className="text-center text-muted">
          <p className="text-lg mb-2">No code generated yet</p>
          <p className="text-sm">
            Use the AI assistant to generate code for your scraping pipeline
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h3 className="text-lg font-semibold">Generated Code</h3>
        <div className="flex space-x-2">
          <Button variant="secondary" size="sm" onClick={handleCopyCode}>
            📋 Copy
          </Button>
          <Button variant="secondary" size="sm" onClick={handleDownloadCode}>
            💾 Download
          </Button>
        </div>
      </div>
      
      <div className="flex-1 overflow-auto p-4">
        <pre className="language-python">
          <code className="language-python">
            {currentPipeline.code}
          </code>
        </pre>
      </div>
    </div>
  );
};

export default CodeViewer;