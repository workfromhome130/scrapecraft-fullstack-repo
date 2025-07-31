import React, { useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble';
import { useChatStore } from '../../store/chatStore';
import LoadingSpinner from '../Common/LoadingSpinner';

const MessageList: React.FC = () => {
  const { messages, isLoading } = useChatStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      
      {isLoading && (
        <div className="flex items-center space-x-2 text-muted">
          <LoadingSpinner />
          <span className="text-sm">AI is thinking...</span>
        </div>
      )}
      
      <div ref={messagesEndRef} />
    </div>
  );
};

export default MessageList;