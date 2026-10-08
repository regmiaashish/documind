import { useEffect, useRef, useState } from 'react';
import type { DemoUser, Document } from './types';
import { deleteDocument, listDocuments, uploadDocument } from './lib/api';
import { useChat } from './hooks/useChat';
import Documents from './components/Documents';
import Icon from './components/Icon';
import Sources from './components/Sources';
import AnswerText from './components/AnswerText';
import TicketConfirmation from './components/TicketConfirmation';

export default function App() {
  /** doc-mind-ai: one page for upload, streamed answers, source passages, and retry. */
  const [user, setUser] = useState<DemoUser>('alice');
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selected, setSelected] = useState('');
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [question, setQuestion] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [retryFile, setRetryFile] = useState<File | null>(null);
  const [deleting, setDeleting] = useState('');
  const [retryDeletion, setRetryDeletion] = useState<Document | null>(null);
  const { messages, busy, ask, clear, removeDocument } = useChat(user);
  const end = useRef<HTMLDivElement>(null);
  const activeDocument = documents.find(item => item.document_id === selected);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    listDocuments(user, controller.signal).then(items => {
      if (controller.signal.aborted) return;
      setDocuments(items);
      setSelected(previous => items.some(item => item.document_id === previous) ? previous : items[0]?.document_id || '');
    }).catch(error => { if (!controller.signal.aborted) setError(error.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [user, refresh]);

  useEffect(() => { if (messages.length) end.current?.scrollIntoView({ block: 'end', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); }, [messages]);

  async function upload(file: File) {
    setError(''); setNotice(''); setRetryFile(null); setRetryDeletion(null);
    if (file.size > 10 * 1024 * 1024) { setError('Choose a file smaller than 10 MB.'); return; }
    setUploading(true);
    try {
      const result = await uploadDocument(file, user);
      setDocuments(previous => [result, ...previous.filter(item => item.document_id !== result.document_id)]);
      setSelected(result.document_id);
      setNotice(result.duplicate ? 'Already uploaded. Ready to ask.' : 'Document ready. Ask your first question.');
    } catch (error) { setRetryFile(file); setError(error instanceof Error ? error.message : 'Upload failed. Please retry.'); }
    finally { setUploading(false); }
  }

  async function remove(document: Document) {
    if (busy || uploading || deleting) return;
    setDeleting(document.document_id); setError(''); setNotice(''); setRetryFile(null); setRetryDeletion(null);
    try {
      await deleteDocument(document.document_id, user);
      const remaining = documents.filter(item => item.document_id !== document.document_id);
      setDocuments(remaining);
      if (selected === document.document_id) { setSelected(remaining[0]?.document_id || ''); setQuestion(''); }
      removeDocument(document.document_id);
      setNotice(`${document.filename} deleted.`);
    } catch (failure) {
      setRetryDeletion(document);
      setError(failure instanceof Error ? failure.message : 'Deletion failed. Please retry.');
    } finally { setDeleting(''); }
  }

  function switchUser(next: DemoUser) {
    if (busy || uploading || deleting) return;
    setRetryFile(null); setRetryDeletion(null); setUser(next); setDocuments([]); setSelected(''); setNotice(''); setError(''); setQuestion('');
  }

  function send(value = question) {
    if (busy || deleting || !value.trim()) return;
    setQuestion('');
    void ask(value.trim(), activeDocument);
  }

  const suggestions = ['Summarize this document', 'What are the main takeaways?', 'List the important dates or deadlines'];
  return <div className="app">
    <header className="topbar">
      <a className="brand" href="/" aria-label="DocuMind home"><span className="brand-mark"><Icon name="file" size={22} /></span>DocuMind</a>
      <span className="workspace-label">Document workspace</span>
      <label className="user-switch"><span className="avatar">{user === 'alice' ? 'A' : 'B'}</span><span className="visually-hidden">Demo user</span>
        <select value={user} onChange={event => switchUser(event.target.value as DemoUser)} disabled={busy || uploading || !!deleting}><option value="alice">Alice · demo</option><option value="bob">Bob · demo</option></select>
      </label>
    </header>
    <div className="workspace">
      <Documents documents={documents} selected={selected} loading={loading} uploading={uploading} disabled={busy || loading || !!deleting}
        deleting={deleting} onDelete={document => void remove(document)}
        notice={notice} error={error} onUpload={upload} onSelect={setSelected} retryLabel={retryDeletion ? 'Retry deletion' : retryFile ? 'Retry upload' : 'Retry loading documents'} onRefresh={() => retryDeletion ? void remove(retryDeletion) : retryFile ? void upload(retryFile) : setRefresh(value => value + 1)} />
      <main className="chat-panel">
        <div className="chat-heading"><div><span className="eyebrow">DOCUMENT CHAT</span><h1>{activeDocument ? 'Ask your document' : 'Your document workspace'}</h1>
          <p>{activeDocument ? <><span className="small-dot" /> {activeDocument.filename}</> : 'Upload a document. Ask a question. See the source.'}</p></div>
          {messages.length > 0 && <button className="quiet-button" onClick={clear} disabled={busy}>Clear chat</button>}
        </div>
        <div className="conversation">
          {!messages.length && <section className="welcome">
            <span className="welcome-icon"><Icon name="spark" size={30} /></span>
            <span className="eyebrow">{activeDocument ? 'READY TO READ' : 'GET STARTED'}</span>
            <h2>{activeDocument ? 'What would you like to know?' : 'Start with a document.'}</h2>
            <p>{activeDocument ? 'Ask a question or start with a summary. Open the sources to check the answer.' : 'Upload a PDF or text file, then ask about its contents. Answers include the passages they came from.'}</p>
            {activeDocument ? <div className="suggestions">{suggestions.map(text => <button key={text} onClick={() => send(text)}>{text}<Icon name="arrow" size={16} /></button>)}</div> :
              <div className="steps"><span><b>01</b> Upload a PDF or text file</span><span><b>02</b> Ask about its contents</span><span><b>03</b> Open the cited passages</span></div>}
            <span className="grounding-note">Answers are based on the selected document.</span>
          </section>}
          {messages.map(message => <article className="exchange" key={message.id}>
            <div className="question-bubble">{message.question}</div>
            <div className="assistant-message"><span className="assistant-avatar"><Icon name="spark" size={17} /></span><div className="answer-content">
              <div className="answer-label">DocuMind{message.result && <span>{(message.result.latency_ms / 1000).toFixed(1)}s · {message.result.refused ? 'No supporting evidence' : message.result.route === 'agent' ? 'Tool result' : 'Cited answer'}</span>}</div>
              <AnswerText text={message.result?.answer || message.draft || (message.error ? '' : 'Looking through your document…')} />
              {message.status && <p className="stream-status" role="status"><span className="pulse-dot" />{message.status}{message.draft ? ' · draft' : ''}</p>}
              {message.result && <Sources citations={message.result.citations} user={user} />}
              {message.result?.confirmation && <TicketConfirmation draft={message.result.confirmation} user={user} />}
              {message.error && <div className="inline-error" role="alert"><p>{message.error}</p><button disabled={busy} onClick={() => {
                const document = documents.find(item => item.document_id === message.documentId);
                void ask(message.question, document, message.id);
              }}>Retry question</button></div>}
            </div></div>
          </article>)}
          <div ref={end} />
        </div>
        <div className="composer-wrap"><form className="composer" onSubmit={event => { event.preventDefault(); send(); }}>
          <textarea aria-label="Your question" placeholder={activeDocument ? 'Ask a question about this document…' : 'Ask about an order or request a support ticket…'} value={question} maxLength={2000}
            disabled={busy || uploading || !!deleting} rows={question.includes('\n') ? 2 : 1} onChange={event => setQuestion(event.target.value)} onKeyDown={event => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send(); }
            }} />
          <button className="send-button" type="submit" aria-label="Send question" disabled={busy || uploading || !!deleting || !question.trim()}><Icon name="send" size={21} /></button>
        </form><p className="composer-note">Check cited sources before relying on an answer. You can also ask about orders or support tickets.</p></div>
      </main>
    </div>
  </div>;
}
