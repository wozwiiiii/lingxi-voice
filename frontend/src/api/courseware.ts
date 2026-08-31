import apiClient from "./client";

// 与后端 schemas/courseware.py 对齐
export interface CoursewareProject {
  id: string;
  title: string;
  description: string | null;
  slides_count: number;
  status: string;
  progress: Record<string, unknown> | null;
  voice_id: string | null;
  created_at: string;
}

export interface CoursewareSlide {
  id: string;
  slide_index: number;
  original_text: string | null;
  edited_text: string | null;
  voice_id: string | null;
  speed: number;
  emotion: string | null;
  style: string | null;
  audio_path: string | null;
  audio_duration_ms: number | null;
  status: string;
}

export interface CoursewareListResponse {
  projects: CoursewareProject[];
  total: number;
}

export interface SlideUpdate {
  edited_text?: string | null;
  voice_id?: string | null;
  speed?: number;
  emotion?: string | null;
  style?: string | null;
  instruction?: string | null;
}

export interface SynthesizeResponse {
  project_id: string;
  status: string;
  message: string;
  progress_ticket?: string;
}

export async function uploadPPTX(file: File, description?: string): Promise<CoursewareProject> {
  const form = new FormData();
  form.append("file", file);
  if (description) form.append("description", description);
  const { data } = await apiClient.post<CoursewareProject>("/courseware/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function listCourseware(type: "preset" | "my"): Promise<CoursewareListResponse> {
  const { data } = await apiClient.get<CoursewareListResponse>(`/courseware?type=${type}`);
  return data;
}

export async function getSlides(projectId: string): Promise<CoursewareSlide[]> {
  const { data } = await apiClient.get<CoursewareSlide[]>(`/courseware/${projectId}/slides`);
  return data;
}

export async function patchSlide(projectId: string, slideIndex: number, updates: SlideUpdate): Promise<CoursewareSlide> {
  const { data } = await apiClient.patch<CoursewareSlide>(`/courseware/${projectId}/slides/${slideIndex}`, updates);
  return data;
}

export async function startSynthesis(projectId: string): Promise<SynthesizeResponse> {
  // Async: returns immediately with status "synthesizing"; track via getSynthesisProgress
  const { data } = await apiClient.post<SynthesizeResponse>(`/courseware/${projectId}/synthesize`, null, {
    timeout: 300000, // Safety net only — submission itself returns immediately
  });
  return data;
}

/**
 * Open an SSE stream that yields synthesis progress `{current, total, status}`.
 *
 * 使用 synthesize 时后端签发的一次性 ticket 作为凭据，而非 JWT。
 * ticket 绑定 user+project，TTL 600s，即使泄露也只能查看该项目进度。
 */
export function getSynthesisProgress(projectId: string, ticket: string): EventSource {
  return new EventSource(`/api/courseware/${projectId}/progress?ticket=${encodeURIComponent(ticket)}`);
}

export async function downloadCourseware(projectId: string): Promise<Blob> {
  const response = await apiClient.get(`/courseware/${projectId}/download`, { responseType: "blob" });
  return response.data;
}
