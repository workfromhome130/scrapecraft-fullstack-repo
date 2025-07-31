import React, { useState } from 'react';
import ChatContainer from '../Chat/ChatContainer';
import PipelinePanel from '../Pipeline/PipelinePanel';
import WorkflowSidebar from '../Workflow/WorkflowSidebar';

const SplitView: React.FC = () => {
  const [splitPosition, setSplitPosition] = useState(40); // 40% for chat
  const [isDragging, setIsDragging] = useState(false);

  const handleMouseDown = () => {
    setIsDragging(true);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    
    const container = e.currentTarget;
    const rect = container.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = (x / rect.width) * 100;
    
    setSplitPosition(Math.min(Math.max(percentage, 20), 80));
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  return (
    <div className="flex h-full">
      {/* Workflow Sidebar */}
      <WorkflowSidebar />
      
      {/* Main Content Area */}
      <div 
        className="flex-1 flex h-full relative"
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {/* Chat Panel */}
        <div 
          className="h-full border-r border-border"
          style={{ width: `${splitPosition}%` }}
        >
          <ChatContainer />
        </div>
        
        {/* Resizer */}
        <div
          className="absolute top-0 h-full w-1 cursor-col-resize hover:bg-primary/50 transition-colors"
          style={{ left: `${splitPosition}%`, marginLeft: '-2px' }}
          onMouseDown={handleMouseDown}
        />
        
        {/* Pipeline Panel */}
        <div 
          className="h-full"
          style={{ width: `${100 - splitPosition}%` }}
        >
          <PipelinePanel />
        </div>
      </div>
    </div>
  );
};

export default SplitView;