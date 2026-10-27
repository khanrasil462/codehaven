export const API_BASE = "http://127.0.0.1:8765/api";

export interface HealthResponse {
  app: string;
  offline_mode: boolean;
  chat_model: string;
  embed_model: string;
  ollama: {
    reachable: boolean;
    models?: string[];
    chat_model_available?: boolean;
    error?: string;
  };
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export type CodeLanguage = "python" | "javascript" | "typescript" | "react";

export interface CodegenRequest {
  prompt: string;
  language: CodeLanguage;
  include_explanation?: boolean;
  stream?: boolean;
}

export interface DebugRequest {
  code: string;
  error_message?: string;
  language: CodeLanguage;
  stream?: boolean;
}

export interface DocumentInfo {
  id: string;
  filename: string;
  file_type: string;
  size_bytes: number;
  chunk_count: number;
  char_count: number;
  created_at: string;
}

export interface SourceChunk {
  doc_id: string;
  filename: string;
  chunk_index: number;
  similarity: number;
  text: string;
}

export interface ExamGenerateRequest {
  title: string;
  subject: string;
  doc_ids?: string[];
  difficulty: "easy" | "medium" | "hard";
  total_marks: number;
  duration_minutes: number;
  include_solutions: boolean;
  model?: string;
  stream?: boolean;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("Backend unreachable");
  return res.json();
}

export async function streamChat(
  messages: ChatMessage[],
  onToken: (token: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, stream: true }),
    signal,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Chat request failed");
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response stream");

  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onToken(decoder.decode(value, { stream: true }));
  }
}

export async function streamCodegen(
  request: CodegenRequest,
  onToken: (token: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_BASE}/codegen/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...request, stream: true }),
    signal,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Codegen request failed");
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response stream");

  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onToken(decoder.decode(value, { stream: true }));
  }
}

export async function streamDebug(
  request: DebugRequest,
  onToken: (token: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_BASE}/debug/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...request, stream: true }),
    signal,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Debug request failed");
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response stream");

  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onToken(decoder.decode(value, { stream: true }));
  }
}

export async function fetchDocuments(): Promise<DocumentInfo[]> {
  const res = await fetch(`${API_BASE}/rag/documents`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Failed to fetch documents");
  }
  return res.json();
}

export async function uploadDocument(file: File): Promise<DocumentInfo> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/rag/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Failed to upload document");
  }
  return res.json();
}

export async function deleteDocument(docId: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/rag/documents/${docId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Failed to delete document");
  }
  return true;
}

export async function streamNotesQuery(
  question: string,
  docId: string | undefined,
  onToken: (token: string) => void,
  onSources?: (sources: SourceChunk[]) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_BASE}/rag/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      doc_id: docId || undefined,
      stream: true,
    }),
    signal,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Notes query failed");
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response stream");

  const decoder = new TextDecoder();
  let buffer = "";
  let sourcesExtracted = false;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      if (!sourcesExtracted && buffer) {
        onToken(buffer);
      }
      break;
    }

    const chunk = decoder.decode(value, { stream: true });
    buffer += chunk;

    if (!sourcesExtracted) {
      if (buffer.startsWith("__SOURCES__:")) {
        const splitIdx = buffer.indexOf("\n\n");
        if (splitIdx !== -1) {
          const jsonStr = buffer.slice("__SOURCES__:".length, splitIdx);
          const remainder = buffer.slice(splitIdx + 2);
          try {
            const sources: SourceChunk[] = JSON.parse(jsonStr);
            if (onSources) onSources(sources);
          } catch {
            // ignore JSON error
          }
          sourcesExtracted = true;
          if (remainder) {
            onToken(remainder);
          }
          buffer = "";
        }
        // Still waiting for complete \n\n delimiter
      } else if (buffer.length < 12 && "__SOURCES__:".startsWith(buffer)) {
        // Partial prefix buffer, wait for next packet
        continue;
      } else {
        // Normal text response without sources header
        sourcesExtracted = true;
        onToken(buffer);
        buffer = "";
      }
    } else {
      onToken(chunk);
    }
  }
}

export async function streamExamGenerate(
  request: ExamGenerateRequest,
  onToken: (token: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_BASE}/rag/exam/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...request, stream: true }),
    signal,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Exam generation failed");
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response stream");

  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onToken(decoder.decode(value, { stream: true }));
  }
}

export function extractCodeBlock(text: string): string {
  const match = text.match(/```(?:\w+)?\n([\s\S]*?)```/);
  return match ? match[1].trim() : text.trim();
}

// --- History & Database Storage Types & APIs ---

export interface ConversationSummary {
  id: string;
  title: string;
  mode: string;
  created_at: string;
  updated_at: string;
}

export interface SavedMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  sources?: SourceChunk[];
  timestamp: string;
}

export interface ConversationDetail {
  id: string;
  title: string;
  mode: string;
  created_at: string;
  updated_at: string;
  messages: SavedMessage[];
}

export interface ExamPaperRecord {
  id: string;
  title: string;
  subject: string;
  difficulty: string;
  total_marks: number;
  duration_minutes: number;
  content_markdown: string;
  created_at: string;
}

export async function fetchConversations(mode?: string): Promise<ConversationSummary[]> {
  const url = mode
    ? `${API_BASE}/history/conversations?mode=${encodeURIComponent(mode)}`
    : `${API_BASE}/history/conversations`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to fetch conversations");
  return res.json();
}

export async function fetchConversation(id: string): Promise<ConversationDetail> {
  const res = await fetch(`${API_BASE}/history/conversations/${id}`);
  if (!res.ok) throw new Error("Failed to load conversation");
  return res.json();
}

export async function createConversation(
  title: string,
  mode: string,
  id?: string
): Promise<ConversationSummary> {
  const res = await fetch(`${API_BASE}/history/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, mode, id }),
  });
  if (!res.ok) throw new Error("Failed to create conversation");
  return res.json();
}

export async function saveMessage(
  convId: string,
  role: string,
  content: string,
  sources?: any,
  id?: string
): Promise<SavedMessage> {
  const res = await fetch(`${API_BASE}/history/conversations/${convId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, content, sources, id }),
  });
  if (!res.ok) throw new Error("Failed to save message");
  return res.json();
}

export async function deleteConversation(id: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/history/conversations/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete conversation");
  return true;
}

export async function fetchExamPapers(): Promise<ExamPaperRecord[]> {
  const res = await fetch(`${API_BASE}/history/exams`);
  if (!res.ok) throw new Error("Failed to fetch exam papers");
  return res.json();
}

export async function saveExamPaper(
  paper: Omit<ExamPaperRecord, "created_at">
): Promise<ExamPaperRecord> {
  const res = await fetch(`${API_BASE}/history/exams`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(paper),
  });
  if (!res.ok) throw new Error("Failed to save exam paper");
  return res.json();
}

export async function deleteExamPaper(id: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/history/exams/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete exam paper");
  return true;
}

// --- Code Execution Runner Types & API ---
export interface ExecuteRequest {
  code: string;
  language: string;
  stdin?: string;
  timeout_seconds?: number;
}

export interface ExecuteResponse {
  status: "success" | "error" | "timeout";
  stdout: string;
  stderr: string;
  exit_code: number;
  execution_time_ms: number;
  language: string;
  runtime_version?: string;
}

export interface RuntimeInfo {
  id: string;
  name: string;
  version: string;
  available: boolean;
  extension: string;
  example_code: string;
}

export async function executeCode(req: ExecuteRequest): Promise<ExecuteResponse> {
  const res = await fetch(`${API_BASE}/runner/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || "Execution request failed");
  }
  return res.json();
}

export async function fetchRuntimes(): Promise<RuntimeInfo[]> {
  const res = await fetch(`${API_BASE}/runner/runtimes`);
  if (!res.ok) throw new Error("Failed to load runtimes");
  return res.json();
}

// --- Image & Diagram Studio Types & API ---
export interface ImageGenerateRequest {
  prompt: string;
  engine?: "auto" | "ai_diffusion" | "vector_diagram";
  style?:
    | "cyberpunk"
    | "photorealistic"
    | "3d_render"
    | "anime"
    | "architecture"
    | "datastructure"
    | "flowchart"
    | "vector"
    | "ui_mockup";
  aspect_ratio?: "16:9" | "1:1" | "4:3";
  theme?: "terminal" | "dark" | "blueprint" | "neon";
  model?: string;
}

export interface ImageItem {
  id: string;
  prompt: string;
  style: string;
  format: string;
  created_at: string;
  svg_content?: string;
  image_url?: string;
  title: string;
  engine?: string;
}

export interface ImageGenerateResponse {
  image: ImageItem;
  explanation: string;
}

export async function generateImage(req: ImageGenerateRequest): Promise<ImageGenerateResponse> {
  const res = await fetch(`${API_BASE}/images/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || "Image generation failed");
  }
  return res.json();
}

export async function fetchImages(): Promise<ImageItem[]> {
  const res = await fetch(`${API_BASE}/images`);
  if (!res.ok) throw new Error("Failed to load images");
  return res.json();
}

export async function deleteImage(id: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/images/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete image");
  return true;
}

// --- Speed Mode Types & API ---
export interface SpeedStatusResponse {
  active_mode: "turbo" | "balanced";
  effective_model: string;
  cpu_threads: number;
  keep_alive: string;
  speed_estimate: string;
  all_models: string[];
}

export async function fetchSpeedStatus(): Promise<SpeedStatusResponse> {
  const res = await fetch(`${API_BASE}/speed`);
  if (!res.ok) throw new Error("Failed to fetch speed status");
  return res.json();
}

export async function setSpeedMode(mode: "turbo" | "balanced"): Promise<{ status: string; active_mode: string; effective_model: string }> {
  const res = await fetch(`${API_BASE}/speed/mode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  if (!res.ok) throw new Error("Failed to set speed mode");
  return res.json();
}
