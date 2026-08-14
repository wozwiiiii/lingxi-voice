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
 * EventSource cannot set custom headers, so the backend `get_progress` endpoint
 * authenticates via a `token` query param instead of the Authorization header
 * (see backend/app/api/courseware.py). Mirror the token source used by the
 * axios interceptor in apiClient.
 */
export function getSynthesisProgress(projectId: string): EventSource {
  const token = localStorage.getItem("access_token");
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  return new EventSource(`/api/courseware/${projectId}/progress${query}`);
}

export async function downloadCourseware(projectId: string): Promise<Blob> {
  const response = await apiClient.get(`/courseware/${projectId}/download`, { responseType: "blob" });
  return response.data;
}
