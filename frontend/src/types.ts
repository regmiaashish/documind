export type DemoUser = 'alice' | 'bob';

export interface Document {
  document_id: string;
  filename: string;
  chunk_count: number;
  chunk_size: 300 | 800;
  page_count: number | null;
  size_bytes: number;
}

export interface Citation {
  source_id: number;
  document_id: string;
  filename: string;
  chunk_index: number;
  page: number | null;
  snippet: string;
}

export interface Answer {
  answer: string;
  citations: Citation[];
  refused: boolean;
  latency_ms: number;
  route?: 'rag' | 'agent';
  confirmation?: { id: string; subject: string; body: string; expires_at: string } | null;
}

export interface Message {
  id: string;
  question: string;
  documentId: string;
  chunkSize: 300 | 800;
  draft: string;
  result?: Answer;
  status: string;
  error?: string;
}
