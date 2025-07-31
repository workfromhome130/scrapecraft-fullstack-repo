import React from 'react';
import MessageList from './MessageList';
import InputArea from './InputArea';

const ChatContainer: React.FC = () => {
  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-border p-4">
        <h2 className="text-lg font-semibold">AI Assistant</h2>
      </div>
      
      <MessageList />
      <InputArea />
    </div>
  );
};

export default ChatContainer;