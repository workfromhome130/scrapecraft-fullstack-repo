import React, { useState, KeyboardEvent } from 'react';
import { useChatStore } from '../../store/chatStore';
import { usePipelineStore } from '../../store/pipelineStore';
import Button from '../Common/Button';

const InputArea: React.FC = () => {
  const [message, setMessage] = useState('');
  const { sendMessage, isLoading } = useChatStore();
  const { currentPipeline } = usePipelineStore();

  const quickActions = [
    {
      label: 'Add URL',
      prompt: 'I want to add a new URL to scrape',
      icon: '🔗'
    },
    {
      label: 'Define Schema',
      prompt: 'Help me define the data schema for extraction',
      icon: '📋'
    },
    {
      label: 'Generate Code',
      prompt: 'Generate the Python code for my scraping pipeline',
      icon: '💻'
    },
    {
      label: 'Run Pipeline',
      prompt: 'Execute the scraping pipeline',
      icon: '▶️'
    }
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isLoading && currentPipeline) {
      sendMessage(message, currentPipeline.id);
      setMessage('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleQuickAction = (action: typeof quickActions[0]) => {
    if (currentPipeline) {
      if (action.label === 'Run Pipeline') {
        // Handle Run Pipeline differently - actually execute it
        usePipelineStore.getState().runPipeline(currentPipeline.id);
      } else {
        sendMessage(action.prompt, currentPipeline.id);
      }
    }
  };

  return (
    <div className="border-t border-border p-4">
      <div className="flex flex-wrap gap-2 mb-3">
        {quickActions.map((action) => (
          <Button
            key={action.label}
            variant="secondary"
            size="sm"
            onClick={() => handleQuickAction(action)}
            disabled={!currentPipeline || isLoading}
          >
            <span className="mr-1">{action.icon}</span>
            {action.label}
          </Button>
        ))}
      </div>
      
      <form onSubmit={handleSubmit}>
        <div className="flex space-x-3">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Press Enter to send, Shift+Enter for new line"
            className="input flex-1 resize-none"
            rows={3}
            disabled={isLoading || !currentPipeline}
          />
          
          <Button
            type="submit"
            variant="primary"
            disabled={!message.trim() || isLoading || !currentPipeline}
          >
            Send
          </Button>
        </div>
      </form>
    </div>
  );
};

export default InputArea;