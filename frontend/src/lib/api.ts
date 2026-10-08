import type { Citation, DemoUser, Document } from '../types';
import { consumeEvents } from './sse.mjs';

function headers(user: DemoUser): HeadersInit {
  return { Authorization: `Bearer dev-${user}-key` };
}

async function check(response: Response): Promise<Response> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error?.message || 'Request failed. Please retry.');
  }
  return response;
}

export async function deleteDocument(documentId: string, user: DemoUser): Promise<void> {
  const response = await fetch(`/api/v1/documents/${documentId}`, { method: 'DELETE', headers: headers(user) });
  if (response.status !== 404) await check(response);
}

export async function listDocuments(user: DemoUser, signal?: AbortSignal): Promise<Document[]> {
  const response = await check(await fetch('/api/v1/documents?limit=100', { headers: headers(user), signal }));
  return response.json();
}

export async function uploadDocument(file: File, user: DemoUser): Promise<Document & { duplicate: boolean }> {
  const data = new FormData();
  data.append('file', file);
  const response = await check(await fetch('/api/v1/documents', { method: 'POST', headers: headers(user), body: data }));
    return response.json();
}

export async function sourcePassage(citation: Citation, user: DemoUser, signal?: AbortSignal): Promise<string> {
  const url = `/api/v1/documents/${citation.document_id}/chunks/${citation.chunk_index}`;
  const response = await check(await fetch(url, { headers: headers(user), signal }));
  return (await response.json()).content;
}

export async function askDocument(
  question: string, documentId: string, chunkSize: number, user: DemoUser,
  signal: AbortSignal, onEvent: (event: string, data: any) => void,
): Promise<void> {
  const response = await check(await fetch('/api/v1/chat-messages', {
    method: 'POST', signal,
    headers: { ...headers(user), 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, document_ids: documentId ? [documentId] : [], chunk_size: chunkSize, stream: true }),
  }));
  await consumeEvents(response, onEvent);
}

export async function confirmTicket(actionId: string, user: DemoUser): Promise<{ id: string }> {
  const response = await check(await fetch(`/api/v1/actions/${actionId}/confirmation`, {
    method: 'POST', headers: headers(user),
  }));
  return response.json();
}
