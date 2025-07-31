import React, { useState } from 'react';
import { usePipelineStore } from '../../store/pipelineStore';
import Button from '../Common/Button';
import Input from '../Common/Input';
import { api } from '../../services/api';

const URLManager: React.FC = () => {
  const [newUrl, setNewUrl] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const { currentPipeline, updatePipeline } = usePipelineStore();

  const handleAddUrl = async () => {
    if (!newUrl.trim() || !currentPipeline) return;

    // Validate URL
    setIsValidating(true);
    try {
      const response = await api.post('/scraping/validate-url', { url: newUrl });
      
      if (response.data.valid) {
        const updatedUrls = [...currentPipeline.urls, newUrl];
        updatePipeline(currentPipeline.id, { urls: updatedUrls });
        setNewUrl('');
      } else {
        alert(`Invalid URL: ${response.data.error || 'URL is not accessible'}`);
      }
    } catch (error) {
      alert('Failed to validate URL');
    } finally {
      setIsValidating(false);
    }
  };

  const handleRemoveUrl = (urlToRemove: string) => {
    if (!currentPipeline) return;
    
    const updatedUrls = currentPipeline.urls.filter(url => url !== urlToRemove);
    updatePipeline(currentPipeline.id, { urls: updatedUrls });
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleAddUrl();
    }
  };

  return (
    <div className="h-full flex flex-col p-4">
      <h3 className="text-lg font-semibold mb-4">URL Management</h3>
      
      {/* Add URL Form */}
      <div className="flex space-x-2 mb-4">
        <Input
          type="url"
          value={newUrl}
          onChange={(e) => setNewUrl(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="https://example.com"
          disabled={!currentPipeline || isValidating}
        />
        <Button
          onClick={handleAddUrl}
          disabled={!newUrl.trim() || !currentPipeline || isValidating}
          variant="primary"
        >
          {isValidating ? 'Validating...' : 'Add URL'}
        </Button>
      </div>
      
      {/* URL List */}
      <div className="flex-1 overflow-y-auto space-y-2">
        {currentPipeline?.urls.length === 0 ? (
          <div className="text-center text-muted py-8">
            <p>No URLs added yet</p>
            <p className="text-sm mt-2">Add URLs to start building your scraping pipeline</p>
          </div>
        ) : (
          currentPipeline?.urls.map((url, index) => (
            <div
              key={index}
              className="card flex items-center justify-between group"
            >
              <div className="flex-1">
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-accent hover:underline break-all"
                >
                  {url}
                </a>
              </div>
              
              <Button
                variant="destructive"
                size="sm"
                onClick={() => handleRemoveUrl(url)}
                className="opacity-0 group-hover:opacity-100 transition-opacity"
              >
                Remove
              </Button>
            </div>
          ))
        )}
      </div>
      
      {/* Summary */}
      {currentPipeline && currentPipeline.urls.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border text-sm text-muted">
          Total URLs: {currentPipeline.urls.length}
        </div>
      )}
    </div>
  );
};

export default URLManager;