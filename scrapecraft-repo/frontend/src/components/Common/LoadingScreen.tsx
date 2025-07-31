import React from 'react';
import LoadingSpinner from './LoadingSpinner';
import logo from '../../assets/logo.png';

const LoadingScreen: React.FC = () => {
  return (
    <div className="fixed inset-0 bg-background flex items-center justify-center z-50">
      <div className="text-center">
        <img src={logo} alt="ScrapeCraft" className="h-16 w-16 mx-auto mb-4 animate-pulse" />
        <h2 className="text-xl font-semibold text-primary mb-2">ScrapeCraft</h2>
        <div className="flex items-center justify-center space-x-2">
          <LoadingSpinner size="sm" />
          <span className="text-muted">Initializing your scraping pipeline...</span>
        </div>
      </div>
    </div>
  );
};

export default LoadingScreen;