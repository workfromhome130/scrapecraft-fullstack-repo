import React, { useEffect, useState } from 'react';
import { usePipelineStore } from '../../store/pipelineStore';
import Button from '../Common/Button';
import Prism from 'prismjs';

const CodeViewer: React.FC = () => {
  const { currentPipeline } = usePipelineStore();
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionResult, setExecutionResult] = useState<any>(null);

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

  const handleExecuteCode = async () => {
    if (!currentPipeline?.code || !currentPipeline?.urls || !currentPipeline?.schema) {
      alert('Please ensure you have URLs and a schema defined before executing.');
      return;
    }

    // Check for API key
    const apiKey = localStorage.getItem('SCRAPEGRAPH_API_KEY');
    if (!apiKey) {
      alert('Please configure your ScrapeGraphAI API key in Settings before executing.');
      return;
    }

    setIsExecuting(true);
    setExecutionResult(null);

    try {
      // Use the pipeline store's runPipeline function
      await usePipelineStore.getState().runPipeline(currentPipeline.id);
      
      // Get the updated pipeline with results
      const updatedPipeline = usePipelineStore.getState().currentPipeline;
      
      if (updatedPipeline?.status === 'completed') {
        setExecutionResult({ 
          success: true, 
          results: updatedPipeline.results 
        });
      } else if (updatedPipeline?.status === 'failed') {
        setExecutionResult({ 
          success: false, 
          errors: ['Pipeline execution failed. Check the console for details.'] 
        });
      }
    } catch (error) {
      console.error('Execution failed:', error);
      setExecutionResult({ 
        success: false, 
        errors: [`Execution failed: ${error}`] 
      });
    } finally {
      setIsExecuting(false);
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
          <Button 
            variant="primary" 
            size="sm" 
            onClick={handleExecuteCode}
            disabled={isExecuting}
          >
            {isExecuting ? '⚡ Executing...' : '▶️ Run'}
          </Button>
          <Button variant="secondary" size="sm" onClick={handleCopyCode}>
            📋 Copy
          </Button>
          <Button variant="secondary" size="sm" onClick={handleDownloadCode}>
            💾 Download
          </Button>
        </div>
      </div>
      
      <div className="flex-1 overflow-auto p-4">
        {executionResult && (
          <div className={`mb-4 p-4 rounded-lg ${executionResult.success ? 'bg-green-900/20 border border-green-500' : 'bg-red-900/20 border border-red-500'}`}>
            <h4 className="font-semibold mb-2">
              {executionResult.success ? '✅ Execution Successful' : '❌ Execution Failed'}
            </h4>
            {executionResult.success ? (
              <div>
                <p className="text-sm mb-2">Scraped {executionResult.results?.length || 0} items successfully!</p>
                <p className="text-xs text-muted">Check the Output tab to see the results.</p>
              </div>
            ) : (
              <div>
                <p className="text-sm text-red-400">
                  {executionResult.errors?.join(', ') || 'Unknown error occurred'}
                </p>
              </div>
            )}
          </div>
        )}
        
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