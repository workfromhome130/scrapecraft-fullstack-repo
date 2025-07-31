import React from 'react';
import Button from '../Common/Button';
import { useChatStore } from '../../store/chatStore';
import { usePipelineStore } from '../../store/pipelineStore';

const QuickActions: React.FC = () => {
  const { sendMessage } = useChatStore();
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

  const handleAction = (prompt: string) => {
    if (currentPipeline) {
      sendMessage(prompt, currentPipeline.id);
    }
  };

  return (
    <div className="flex flex-wrap gap-2">
      {quickActions.map((action) => (
        <Button
          key={action.label}
          variant="secondary"
          size="sm"
          onClick={() => handleAction(action.prompt)}
          disabled={!currentPipeline}
        >
          <span className="mr-1">{action.icon}</span>
          {action.label}
        </Button>
      ))}
    </div>
  );
};

export default QuickActions;