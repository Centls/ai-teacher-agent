'use client';

import { useChat } from 'ai/react';
import { Send, User, Bot } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card } from '@/components/ui/card';
import ReactMarkdown from 'react-markdown';
import { useEffect, useRef } from 'react';

interface ChatInterfaceProps {
  selectedTeacher: string;
}

export function ChatInterface({ selectedTeacher }: ChatInterfaceProps) {
  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
    api: 'http://localhost:8001/api/chat',
    body: {
      teacher_id: selectedTeacher,
    },
  });
  
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto p-2 md:p-4">
      <Card className="flex-1 mb-4 p-4 overflow-hidden flex flex-col bg-white/50 backdrop-blur-sm border-slate-200 shadow-sm">
        <ScrollArea className="flex-1 pr-4" ref={scrollRef}>
          <div className="space-y-4">
            {messages.length === 0 && (
              <div className="text-center text-slate-500 mt-20">
                <h2 className="text-2xl font-semibold mb-2">AI Teacher Nexus</h2>
                <p>Current Teacher: <span className="font-bold capitalize">{selectedTeacher}</span></p>
                <p>Start a conversation to begin.</p>
              </div>
            )}
            
            {messages.map(m => (
              <div key={m.id} className={`flex gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                  m.role === 'user' ? 'bg-blue-500 text-white' : 'bg-emerald-500 text-white'
                }`}>
                  {m.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                </div>
                
                <div className={`rounded-lg p-3 max-w-[80%] ${
                  m.role === 'user' 
                    ? 'bg-blue-500 text-white' 
                    : 'bg-white border border-slate-200 shadow-sm'
                }`}>
                  <div className={`prose prose-sm ${m.role === 'user' ? 'prose-invert' : ''}`}>
                    <ReactMarkdown>{m.content}</ReactMarkdown>
                  </div>
                </div>
              </div>
            ))}
            
            {isLoading && (
              <div className="flex gap-3">
                 <div className="w-8 h-8 rounded-full bg-emerald-500 text-white flex items-center justify-center shrink-0">
                  <Bot size={16} />
                </div>
                <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-sm">
                  <span className="animate-pulse">Thinking...</span>
                </div>
              </div>
            )}
          </div>
        </ScrollArea>
      </Card>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input
          value={input}
          onChange={handleInputChange}
          placeholder="Type your message..."
          className="flex-1 bg-white/80 backdrop-blur-sm"
        />
        <Button type="submit" disabled={isLoading || !input.trim()}>
          <Send size={18} />
          <span className="sr-only">Send</span>
        </Button>
      </form>
    </div>
  );
}
