import React, { useEffect, useState } from 'react';
import SplitView from './components/Layout/SplitView';
import Header from './components/Layout/Header';
import StatusBar from './components/Layout/StatusBar';
import LoadingScreen from './components/Common/LoadingScreen';
import ApprovalManager from './components/Workflow/ApprovalManager';
import { useWebSocket } from './hooks/useWebSocket';
import { usePipelineStore } from './store/pipelineStore';
import Prism from 'prismjs';
import 'prismjs/components/prism-python';
import 'prismjs/themes/prism-tomorrow.css';

function App() {
  const { currentPipeline, createPipeline, fetchPipelines, isLoading } = usePipelineStore();
  const [isInitializing, setIsInitializing] = useState(true);
  
  useEffect(() => {
    // Initialize PrismJS
    Prism.highlightAll();
    
    // Auto-create a pipeline on first load
    const initializePipeline = async () => {
      await fetchPipelines();
      
      // If no current pipeline, create one automatically
      if (!currentPipeline) {
        await createPipeline({
          name: 'My Scraping Pipeline',
          description: 'Ready to scrape the web!'
        });
      }
      
      // Small delay to ensure smooth loading experience
      setTimeout(() => {
        setIsInitializing(false);
      }, 500);
    };
    
    initializePipeline();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Initialize WebSocket connection
  useWebSocket(currentPipeline?.id || 'default');

  // Show loading screen during initialization
  if (isInitializing || (isLoading && !currentPipeline)) {
    return <LoadingScreen />;
  }

  return (
    <div className="h-screen flex flex-col bg-background text-foreground">
      <Header />
      <div className="flex-1 overflow-hidden">
        <SplitView />
      </div>
      <StatusBar />
      <ApprovalManager />
    </div>
  );
}

export default App;