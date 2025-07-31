import React, { useState } from 'react';
import URLManager from './URLManager';
import SchemaEditor from './SchemaEditor';
import CodeViewer from './CodeViewer';
import OutputView from './OutputView';
import Button from '../Common/Button';

type TabType = 'urls' | 'schema' | 'code' | 'output';

const PipelinePanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('urls');

  const tabs = [
    { id: 'urls' as TabType, label: 'URLs', icon: '🔗' },
    { id: 'schema' as TabType, label: 'Schema', icon: '📋' },
    { id: 'code' as TabType, label: 'Code', icon: '💻' },
    { id: 'output' as TabType, label: 'Output', icon: '📊' }
  ];

  const renderContent = () => {
    switch (activeTab) {
      case 'urls':
        return <URLManager />;
      case 'schema':
        return <SchemaEditor />;
      case 'code':
        return <CodeViewer />;
      case 'output':
        return <OutputView />;
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Tab Navigation */}
      <div className="border-b border-border">
        <div className="flex space-x-1 p-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-t-md text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-background text-foreground border-b-2 border-primary'
                  : 'text-muted hover:text-foreground hover:bg-secondary'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      
      {/* Tab Content */}
      <div className="flex-1 overflow-hidden">
        {renderContent()}
      </div>
    </div>
  );
};

export default PipelinePanel;