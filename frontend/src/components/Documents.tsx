import { useRef } from 'react';
import type { Document } from '../types';
import Icon from './Icon';

interface Props {
  documents: Document[];
  selected: string;
  loading: boolean;
  uploading: boolean;
  disabled: boolean;
  notice: string;
  error: string;
  onSelect: (id: string) => void;
  onUpload: (file: File) => void;
  onRefresh: () => void;
  retryLabel: string;
  deleting: string;
  onDelete: (document: Document) => void;
}

export default function Documents(props: Props) {
  const input = useRef<HTMLInputElement>(null);
  return <aside className="documents-panel" aria-label="Your documents">
    <div className="panel-heading"><h2>Your documents</h2><span className="count">{props.documents.length}</span></div>
    <p className="panel-description">Choose a document to ask about.</p>
    <input ref={input} type="file" accept=".pdf,.txt,application/pdf,text/plain" className="visually-hidden" aria-label="Choose PDF or text file"
      onChange={event => { const file = event.target.files?.[0]; if (file) props.onUpload(file); event.target.value = ''; }} />
    <button className="upload-zone" disabled={props.disabled || props.uploading} onClick={() => input.current?.click()}>
      <span className="upload-icon"><Icon name="upload" size={22} /></span>
      <strong>{props.uploading ? 'Reading your document…' : 'Upload a document'}</strong>
      <span>PDF or text · up to 10 MB</span>
    </button>
    {props.notice && <p className="notice" role="status">{props.notice}</p>}
    {props.error && <div className="inline-error" role="alert"><p>{props.error}</p><button disabled={props.uploading || props.disabled} onClick={props.onRefresh}>{props.retryLabel}</button></div>}
    <div className="document-list" aria-busy={props.loading}>
      {props.loading ? <p className="muted">Loading documents…</p> : props.documents.length ? props.documents.map(document =>
        <div className={`document-item ${props.selected === document.document_id ? 'selected' : ''}`} key={document.document_id}>
        <button className="document-select"
          disabled={props.disabled} onClick={() => props.onSelect(document.document_id)} aria-pressed={props.selected === document.document_id}>
          <span className="document-icon"><Icon name="file" /></span>
          <span className="document-name"><strong title={document.filename}>{document.filename}</strong><small>{document.page_count ? `${document.page_count} pages · ` : ''}{document.chunk_count} passages</small></span>
          {props.selected === document.document_id && <span className="selected-dot" />}
        </button>
        <button className="document-delete" disabled={props.disabled || props.uploading} aria-label={`Delete ${document.filename}`} title={`Delete ${document.filename}`}
          onClick={() => props.onDelete(document)}>{props.deleting === document.document_id ? '…' : <Icon name="trash" size={17} />}</button>
        </div>) : <div className="empty-documents"><Icon name="file" size={27} /><p>No documents yet</p><small>Add your first document above.</small></div>}
    </div>
    <div className="privacy-note"><span className="small-dot" /><p>Only documents belonging to the selected demo user are available.</p></div>
  </aside>;
}
