import React, { useState } from 'react';
import Button from '../Common/Button';
import SettingsModal from '../Settings/SettingsModal';
import { usePipelineStore } from '../../store/pipelineStore';
import logo from '../../assets/logo.png';

const Header: React.FC = () => {
  const { currentPipeline, createPipeline } = usePipelineStore();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  return (
    <>
    <header className="bg-secondary border-b border-border px-6 py-3 flex items-center justify-between">
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2">
          <img src={logo} alt="ScrapeCraft" className="h-8 w-8" />
          <h1 className="text-xl font-semibold text-primary">ScrapeCraft</h1>
        </div>
        {currentPipeline && (
          <span className="text-sm text-muted">
            {currentPipeline.name}
          </span>
        )}
      </div>
      
      <div className="flex items-center space-x-3">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => createPipeline({
            name: `Pipeline ${Date.now()}`,
            description: 'New scraping pipeline'
          })}
        >
          New Pipeline
        </Button>
        <Button 
          variant="secondary" 
          size="sm"
          onClick={() => setIsSettingsOpen(true)}
        >
          Settings
        </Button>
      </div>
    </header>
    
    <SettingsModal 
      isOpen={isSettingsOpen}
      onClose={() => setIsSettingsOpen(false)}
    />
    </>
  );
};

export default Header;