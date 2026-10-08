import { useState } from 'react';
import type { Answer, DemoUser } from '../types';
import { confirmTicket } from '../lib/api';

export default function TicketConfirmation({ draft, user }: { draft: NonNullable<Answer['confirmation']>; user: DemoUser }) {
  const [busy, setBusy] = useState(false);
  const [ticket, setTicket] = useState('');
  const [error, setError] = useState('');
  async function confirm() {
    setBusy(true); setError('');
    try { setTicket((await confirmTicket(draft.id, user)).id); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Confirmation failed. Please retry.'); }
    finally { setBusy(false); }
  }
  return <section className="ticket-draft" aria-label="Ticket confirmation">
    <h3>{draft.subject}</h3><p>{draft.body}</p>
    {ticket ? <p role="status">Ticket created: {ticket}</p> : <>
      <p>Draft expires at {new Date(draft.expires_at).toLocaleTimeString()}.</p>
      <button className="quiet-button" disabled={busy} onClick={() => void confirm()}>{busy ? 'Confirming…' : 'Confirm ticket'}</button>
    </>}
    {error && <p className="inline-error" role="alert">{error}</p>}
  </section>;
}
