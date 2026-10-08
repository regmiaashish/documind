import { useEffect, useRef, useState } from 'react';
import type { DemoUser, Document, Message } from '../types';
import { askDocument } from '../lib/api';

export function useChat(user: DemoUser) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    setMessages([]);
    setBusy(false);
    return () => controller.current?.abort();
  }, [user]);

  async function ask(question: string, document?: Document, retryId?: string) {
    if (controller.current) return;
    const id = retryId || crypto.randomUUID();
    const message: Message = { id, question, documentId: document?.document_id || '', chunkSize: document?.chunk_size || 300, draft: '', status: 'Finding relevant passages' };
    setMessages(previous => retryId ? previous.map(item => item.id === id ? message : item) : [...previous, message]);
    setBusy(true);
    const active = new AbortController();
    controller.current = active;
    const update = (change: Partial<Message> | ((old: Message) => Partial<Message>)) => {
      if (active.signal.aborted) return;
      setMessages(previous => previous.map(item => item.id === id ? { ...item, ...(typeof change === 'function' ? change(item) : change) } : item));
    };
    try {
      await askDocument(question, document?.document_id || '', document?.chunk_size || 300, user, active.signal, (event, data) => {
        if (event === 'status') update({ status: data.message });
        if (event === 'token') update(old => ({ draft: old.draft + data.text }));
        if (event === 'answer') update({ result: data, draft: '', status: '' });
      });
    } catch (error) {
      if (!active.signal.aborted) update({ draft: '', result: undefined, status: '', error: error instanceof Error ? error.message : 'The answer failed. Please retry.' });
    } finally {
      if (controller.current === active) { controller.current = null; setBusy(false); }
    }
  }

  function clear() { if (!busy) setMessages([]); }
  function removeDocument(documentId: string) {
    setMessages(previous => previous.filter(message => message.documentId !== documentId && !message.result?.citations.some(citation => citation.document_id === documentId)));
  }
  return { messages, busy, ask, clear, removeDocument };
}
