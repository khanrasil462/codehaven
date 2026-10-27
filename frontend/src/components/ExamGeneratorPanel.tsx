import { useEffect, useRef, useState } from "react";
import {
  fetchDocuments,
  saveExamPaper,
  streamExamGenerate,
  type DocumentInfo,
  type ExamGenerateRequest,
  type ExamPaperRecord,
} from "../api/client";
import { Markdown } from "../lib/markdown";

interface ExamGeneratorPanelProps {
  initialExam?: ExamPaperRecord | null;
}

export function ExamGeneratorPanel({ initialExam }: ExamGeneratorPanelProps = {}) {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [subject, setSubject] = useState("Data Structures & Algorithms");
  const [title, setTitle] = useState("College Semester Reference Examination Paper");
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");
  const [totalMarks, setTotalMarks] = useState<number>(50);
  const [durationMinutes, setDurationMinutes] = useState<number>(90);
  const [includeSolutions, setIncludeSolutions] = useState(true);

  const [generating, setGenerating] = useState(false);
  const [examContent, setExamContent] = useState<string>("");
  const [showSolutions, setShowSolutions] = useState(true);
  const [copied, setCopied] = useState(false);

  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (initialExam) {
      setSubject(initialExam.subject);
      setTitle(initialExam.title);
      setDifficulty(initialExam.difficulty as any);
      setTotalMarks(initialExam.total_marks);
      setDurationMinutes(initialExam.duration_minutes);
      setExamContent(initialExam.content_markdown);
    }
  }, [initialExam]);

  useEffect(() => {
    fetchDocuments().then((docs) => {
      setDocuments(docs);
      if (docs.length > 0 && !initialExam) {
        // Infer default subject if notes filename is informative
        const firstName = docs[0].filename.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ");
        if (firstName.length > 3) {
          setSubject(firstName);
        }
      }
    }).catch(() => {});
  }, []);

  async function handleGenerate() {
    if (documents.length === 0) {
      alert("Please upload at least one note in the 'Notes & Q&A' tab first!");
      return;
    }

    setGenerating(true);
    setExamContent("");
    abortRef.current = new AbortController();

    const req: ExamGenerateRequest = {
      title,
      subject,
      doc_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
      difficulty,
      total_marks: totalMarks,
      duration_minutes: durationMinutes,
      include_solutions: includeSolutions,
    };

    try {
      let fullExam = "";
      await streamExamGenerate(
        req,
        (token) => {
          fullExam += token;
          setExamContent(fullExam);
        },
        abortRef.current.signal
      );

      // Auto-save generated exam to local SQLite database
      if (fullExam.trim()) {
        saveExamPaper({
          id: crypto.randomUUID(),
          title,
          subject,
          difficulty,
          total_marks: totalMarks,
          duration_minutes: durationMinutes,
          content_markdown: fullExam,
        }).catch(console.error);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to generate exam paper";
      setExamContent((prev) => prev + `\n\n[Error: ${msg}]`);
    } finally {
      setGenerating(false);
      abortRef.current = null;
    }
  }

  function handleStop() {
    abortRef.current?.abort();
    setGenerating(false);
  }

  function handlePrint() {
    window.print();
  }

  function handleCopy() {
    navigator.clipboard.writeText(examContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownload() {
    const blob = new Blob([examContent], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${subject.replace(/\s+/g, "_")}_Reference_Exam_Paper.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // Filter content to hide solutions if user toggled it off
  const displayContent = showSolutions
    ? examContent
    : examContent.split(/(?:###?|\*\*|##)\s*SECTION\s*D(?::|\s|-).*/i)[0];

  return (
    <div className="layout exam-layout">
      {/* Configuration Sidebar */}
      <section className="exam-config-sidebar">
        <div className="panel-header">
          <strong>Exam Settings</strong>
        </div>

        <div className="config-form">
          <label className="form-group">
            <span>Subject / Course Title</span>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="e.g. Operating Systems, Web Technologies"
              disabled={generating}
            />
          </label>

          <label className="form-group">
            <span>Paper Title</span>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Mid-Semester Assessment"
              disabled={generating}
            />
          </label>

          <label className="form-group">
            <span>Target Notes</span>
            <select
              value={selectedDocIds[0] ?? ""}
              onChange={(e) => setSelectedDocIds(e.target.value ? [e.target.value] : [])}
              disabled={generating}
            >
              <option value="">All Uploaded Notes ({documents.length})</option>
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename}
                </option>
              ))}
            </select>
          </label>

          <div className="form-group">
            <span>Difficulty Level</span>
            <div className="difficulty-pills">
              {(["easy", "medium", "hard"] as const).map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  className={`diff-pill ${difficulty === lvl ? "active" : ""}`}
                  onClick={() => setDifficulty(lvl)}
                  disabled={generating}
                >
                  {lvl === "easy" ? "Easy" : lvl === "medium" ? "University" : "Hard"}
                </button>
              ))}
            </div>
          </div>

          <div className="form-row">
            <label className="form-group">
              <span>Total Marks</span>
              <select
                value={totalMarks}
                onChange={(e) => setTotalMarks(Number(e.target.value))}
                disabled={generating}
              >
                <option value={20}>20 Marks (Quiz)</option>
                <option value={50}>50 Marks (Mid-Term)</option>
                <option value={75}>75 Marks (Standard)</option>
                <option value={100}>100 Marks (Finals)</option>
              </select>
            </label>

            <label className="form-group">
              <span>Duration</span>
              <select
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
                disabled={generating}
              >
                <option value={30}>30 Minutes</option>
                <option value={60}>60 Minutes (1 hr)</option>
                <option value={90}>90 Minutes (1.5 hrs)</option>
                <option value={180}>180 Minutes (3 hrs)</option>
              </select>
            </label>
          </div>

          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={includeSolutions}
              onChange={(e) => setIncludeSolutions(e.target.checked)}
              disabled={generating}
            />
            <span>Include Model Answers & Step-by-Step Marking Scheme</span>
          </label>

          <div className="generate-actions">
            {generating ? (
              <button type="button" className="secondary" onClick={handleStop}>
                Stop Generation
              </button>
            ) : (
              <button
                type="button"
                className="primary-btn"
                onClick={handleGenerate}
                disabled={documents.length === 0}
              >
                Set Reference Exam Paper
              </button>
            )}
          </div>

          {documents.length === 0 && (
            <div className="warning-box">
              No notes uploaded yet. Switch to the <strong>Notes & Q&A</strong> tab to upload lecture notes or syllabus first.
            </div>
          )}
        </div>
      </section>

      {/* Main Exam Paper Sheet View */}
      <section className="exam-view-section">
        <div className="panel-header">
          <div className="exam-header-meta">
            <strong>Exam Paper Preview</strong>
            {examContent && (
              <span className="exam-badge">
                {totalMarks} Marks | {durationMinutes} mins | {difficulty.toUpperCase()}
              </span>
            )}
          </div>

          {examContent && (
            <div className="exam-toolbar-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setShowSolutions(!showSolutions)}
              >
                {showSolutions ? "Hide Answers" : "Show Answers"}
              </button>
              <button type="button" className="secondary" onClick={handleCopy}>
                {copied ? "Copied!" : "Copy"}
              </button>
              <button type="button" className="secondary" onClick={handleDownload}>
                Download .md
              </button>
              <button type="button" className="print-btn" onClick={handlePrint}>
                Print / Save PDF
              </button>
            </div>
          )}
        </div>

        <div className="exam-sheet-container">
          {!examContent && !generating ? (
            <div className="empty-exam-state">
              <div className="empty-icon"></div>
              <h3>Automated Reference Exam Paper Setter</h3>
              <p>
                Configure the exam parameters on the left and click <strong>Set Reference Exam Paper</strong>.
              </p>
              <ul className="exam-features-list">
                <li><strong>Section A (MCQs)</strong> with 4 choices & answer keys</li>
                <li><strong>Section B (Short Answer)</strong> for core definitions & conceptual checks</li>
                <li><strong>Section C (Long Questions)</strong> with comprehensive coding problems</li>
                <li><strong>Complete Marking Scheme</strong> with point-by-point rubrics</li>
                <li><strong>Print-Ready Format</strong> to export directly as college question paper</li>
              </ul>
            </div>
          ) : (
            <div className="exam-sheet">
              {generating && (
                <div className="generating-indicator">
                  <div className="spinner"></div>
                  <p>
                    {examContent
                      ? `Writing the paper… ${examContent.split(/\s+/).filter(Boolean).length} words so far`
                      : "Reading your notes and drafting the paper…"}
                  </p>
                </div>
              )}
              <div className="exam-rendered-text">
                <Markdown text={displayContent} />
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
