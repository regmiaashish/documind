import { useEffect, useState } from 'react';
import type { Citation, DemoUser } from '../types';
import { sourcePassage } from '../lib/api';
import Icon from './Icon';

function Source({ citation, user }: { citation: Citation; user: DemoUser }) {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState('');
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!open || content) return;
    const controller = new AbortController();
    setError('');
    sourcePassage(citation, user, controller.signal).then(setContent).catch(error => {
      if (!controller.signal.aborted) setError(error.message);
    });
    return () => controller.abort();
  }, [open, content, citation, user, attempt]);
  return <div className={`source-card ${open ? 'expanded' : ''}`}>
    <button className="source-heading" onClick={() => setOpen(!open)} aria-expanded={open}>
      <span className="source-number">{citation.source_id}</span><Icon name="file" size={16} />
      <strong>{citation.filename}</strong><span className="source-location">{citation.page ? `Page ${citation.page} · ` : ''}Passage {citation.chunk_index + 1}</span>
      <span className="expand-mark">{open ? '−' : '+'}</span>
    </button>
    {open && <div className="source-content">{error ? <><p role="alert">{error}</p><button onClick={() => setAttempt(attempt + 1)}>Retry source</button></> : <p>{content || 'Loading source passage…'}</p>}</div>}
  </div>;
}

export default function Sources({ citations, user }: { citations: Citation[]; user: DemoUser }) {
  if (!citations.length) return null;
  return <div className="sources"><h4>Sources <span>{citations.length}</span></h4>{citations.map(citation => <Source key={`${citation.document_id}-${citation.chunk_index}`} citation={citation} user={user} />)}</div>;
}
