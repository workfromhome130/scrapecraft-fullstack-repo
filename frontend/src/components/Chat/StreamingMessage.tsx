import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import logo from '../../assets/logo.png';

interface StreamingMessageProps {
  content: string;
  isComplete: boolean;
  timestamp: string;
}

const StreamingMessage: React.FC<StreamingMessageProps> = ({ 
  content, 
  isComplete, 
  timestamp 
}) => {
  // Just display the content directly since backend is already streaming
  const displayedContent = content;
  
  return (
    <div className="flex flex-col items-start mb-4 animate-fade-in">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-medium flex items-center space-x-1">
          <img src={logo} alt="AI" className="h-4 w-4" />
          <span>ScrapeCraft AI</span>
        </span>
        <span className="text-xs text-muted">
          {new Date(timestamp).toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit' 
          })}
        </span>
      </div>
      
      <div className="max-w-[80%] rounded-lg p-4 bg-secondary relative">
        {!isComplete && (
          <div className="absolute -bottom-1 right-2">
            <div className="flex space-x-1">
              <div className="w-2 h-2 bg-accent rounded-full animate-bounce" 
                   style={{ animationDelay: '0ms' }}></div>
              <div className="w-2 h-2 bg-accent rounded-full animate-bounce" 
                   style={{ animationDelay: '150ms' }}></div>
              <div className="w-2 h-2 bg-accent rounded-full animate-bounce" 
                   style={{ animationDelay: '300ms' }}></div>
            </div>
          </div>
        )}
        
        <div className="text-sm">
          <div className="prose prose-sm prose-invert max-w-none
            prose-headings:text-foreground prose-headings:font-semibold
            prose-p:text-foreground prose-p:leading-relaxed
            prose-a:text-accent prose-a:no-underline hover:prose-a:underline
            prose-strong:text-foreground prose-strong:font-semibold
            prose-code:text-accent prose-code:bg-code-bg prose-code:px-1 prose-code:py-0.5 prose-code:rounded
            prose-pre:bg-code-bg prose-pre:text-code-text prose-pre:p-4 prose-pre:rounded-md
            prose-ol:text-foreground prose-ul:text-foreground
            prose-li:text-foreground prose-li:marker:text-muted">
            <ReactMarkdown 
              remarkPlugins={[remarkGfm]}
              components={{
                code({className, children, ...props}: any) {
                  const match = /language-(\w+)/.exec(className || '');
                  const isInline = !match;
                  
                  if (!isInline && match) {
                    return (
                      <pre className="bg-code-bg text-code-text p-4 rounded-md overflow-x-auto my-2">
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
              {displayedContent}
            </ReactMarkdown>
            {!isComplete && (
              <span className="inline-block w-2 h-4 ml-1 bg-accent animate-pulse" />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default StreamingMessage;