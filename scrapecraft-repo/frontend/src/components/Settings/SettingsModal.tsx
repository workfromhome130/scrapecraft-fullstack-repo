import React, { useState, useEffect } from 'react';
import Button from '../Common/Button';
import Input from '../Common/Input';
import { api } from '../../services/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const [openrouterKey, setOpenrouterKey] = useState('');
  const [scrapegraphKey, setScrapegraphKey] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState('');

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    
    document.addEventListener('keydown', handleEsc);
    return () => document.removeEventListener('keydown', handleEsc);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSave = async () => {
    setIsSaving(true);
    setSavedMessage('');
    
    try {
      await api.post('/auth/api-keys', {
        openrouter_key: openrouterKey,
        scrapegraph_key: scrapegraphKey
      });
      
      setSavedMessage('API keys saved successfully!');
      setTimeout(() => {
        setSavedMessage('');
      }, 3000);
    } catch (error) {
      setSavedMessage('Failed to save API keys');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="fixed inset-0 flex items-center justify-center z-50 p-4">
        <div className="bg-secondary rounded-lg p-6 w-full max-w-md animate-slide-up">
          <h2 className="text-xl font-semibold mb-4">Settings</h2>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                OpenRouter API Key
              </label>
              <Input
                type="password"
                value={openrouterKey}
                onChange={(e) => setOpenrouterKey(e.target.value)}
                placeholder="sk-or-v1-..."
              />
              <p className="text-xs text-muted mt-1">
                Get your key from <a 
                  href="https://openrouter.ai/keys" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  openrouter.ai/keys
                </a>
              </p>
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-2">
                ScrapeGraphAI API Key
              </label>
              <Input
                type="password"
                value={scrapegraphKey}
                onChange={(e) => setScrapegraphKey(e.target.value)}
                placeholder="sgai-..."
              />
              <p className="text-xs text-muted mt-1">
                Get your key from <a 
                  href="https://scrapegraphai.com/keys" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  scrapegraphai.com
                </a>
              </p>
            </div>
            
            {savedMessage && (
              <div className={`text-sm ${savedMessage.includes('success') ? 'text-success' : 'text-error'}`}>
                {savedMessage}
              </div>
            )}
          </div>
          
          <div className="flex justify-end space-x-3 mt-6">
            <Button
              variant="secondary"
              onClick={onClose}
              disabled={isSaving}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleSave}
              disabled={isSaving || (!openrouterKey && !scrapegraphKey)}
            >
              {isSaving ? 'Saving...' : 'Save Keys'}
            </Button>
          </div>
        </div>
      </div>
    </>
  );
};

export default SettingsModal;