import React from 'react';
import { format } from 'date-fns';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChatMessage } from '../../types';
import clsx from 'clsx';
import logo from '../../assets/logo.png';

interface MessageBubbleProps {
  message: ChatMessage;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user';

  return (
    <div className={clsx('flex flex-col', isUser ? 'items-end' : 'items-start', 'mb-4')}>
      <div className={clsx('flex items-center gap-2 mb-1', isUser ? 'flex-row-reverse' : 'flex-row')}>
        <span className="text-xs font-medium flex items-center space-x-1">
          {!isUser && (
            <img src={logo} alt="AI" className="h-4 w-4" />
          )}
          <span>{isUser ? 'You' : 'ScrapeCraft AI'}</span>
        </span>
        <span className="text-xs text-muted">
          {format(new Date(message.timestamp), 'HH:mm')}
        </span>
      </div>
      <div className={clsx(
        'max-w-[80%] rounded-lg p-4 animate-slide-up',
        isUser ? 'bg-primary text-white' : 'bg-secondary'
      )}>
        
        <div className="text-sm">
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose prose-sm prose-invert max-w-none
              prose-headings:text-foreground prose-headings:font-semibold
              prose-p:text-foreground prose-p:leading-relaxed
              prose-a:text-accent prose-a:no-underline hover:prose-a:underline
              prose-strong:text-foreground prose-strong:font-semibold
              prose-code:text-accent prose-code:bg-code-bg prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:content-[''] prose-code:after:content-['']
              prose-pre:bg-code-bg prose-pre:text-code-text prose-pre:p-4 prose-pre:rounded-md prose-pre:overflow-x-auto
              prose-ol:text-foreground prose-ul:text-foreground
              prose-li:text-foreground prose-li:marker:text-muted
              prose-blockquote:text-muted prose-blockquote:border-l-4 prose-blockquote:border-border prose-blockquote:pl-4">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({className, children, ...props}: any) {
                    const match = /language-(\w+)/.exec(className || '');
                    const isInline = !match;
                    
                    if (!isInline && match) {
                      return (
                        <pre className="bg-code-bg text-code-text p-4 rounded-md overflow-x-auto">
                          <code className={className} {...props}>
                            {children}
                          </code>
                        </pre>
                      );
                    }
                    
                    return (
                      <code className="text-accent bg-code-bg px-1 py-0.5 rounded text-sm" {...props}>
                        {children}
                      </code>
                    );
                  }
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>
        
        {message.metadata?.toolsUsed && (
          <div className="mt-2 pt-2 border-t border-white/20">
            <span className="text-xs opacity-70">
              Tools used: {message.metadata.toolsUsed.join(', ')}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

export default MessageBubble;