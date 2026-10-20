import { FileText, Upload } from "lucide-react";
import type { Document } from "../api/types";
import StatusBadge from "../components/StatusBadge";

/** The procedure library: documents indexed for investigations (RAG). */
export default function ProceduresPage({
  documents,
  canWrite,
  uploading,
  onUpload,
}: {
  documents: Document[] | undefined;
  canWrite: boolean;
  uploading: boolean;
  onUpload: (file: File) => void;
}) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>Procedure library</h2>
        {canWrite && (
          <label className="button primary">
            <Upload size={15} /> Add a document
            <input
              type="file"
              accept=".pdf,.txt"
              hidden
              disabled={uploading}
              onChange={(e) => {
                if (e.target.files?.[0]) onUpload(e.target.files[0]);
                e.target.value = "";
              }}
            />
          </label>
        )}
      </div>
      <p className="section-description">
        Text-based PDF or UTF-8 TXT. Each passage keeps its document name and
        page number. Scanned PDFs require OCR, which is not included in this
        version.
      </p>
      {!documents?.length ? (
        <div className="empty">
          <FileText />
          <h3>Add your first procedure</h3>
          <p>A sample demo procedure is provided in the examples folder.</p>
        </div>
      ) : (
        documents.map((doc) => (
          <div className="document-row" key={doc.id}>
            <FileText />
            <div>
              <strong>{doc.name}</strong>
              <small>{doc.id.slice(0, 8)}</small>
            </div>
            <StatusBadge value={doc.status} />
          </div>
        ))
      )}
    </section>
  );
}
