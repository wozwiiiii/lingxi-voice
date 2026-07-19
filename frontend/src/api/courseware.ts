import apiClient from "./client";

export interface CoursewareProject {
  id: string;
  title: string;
  description: string | null;
  slides_count: number;
  status: string;
  progress: any;
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

export async function uploadPPTX(file: File, description?: string): Promise<CoursewareProject> {
  const form = new FormData();
  form.append("file", file);
  if (description) form.append("description", description);
  const { data } = await apiClient.post<CoursewareProject>("/courseware/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function listCourseware(type: "preset" | "my"): Promise<{ projects: CoursewareProject[]; total: number }> {
  const { data } = await apiClient.get(`/courseware?type=${type}`);
  return data;
}

export async function getSlides(projectId: string): Promise<CoursewareSlide[]> {
  const { data } = await apiClient.get(`/courseware/${projectId}/slides`);
  return data;
}

export async function patchSlide(projectId: string, slideIndex: number, updates: any): Promise<CoursewareSlide> {
  const { data } = await apiClient.patch(`/courseware/${projectId}/slides/${slideIndex}`, updates);
  return data;
}

export async function startSynthesis(projectId: string): Promise<any> {
  const { data } = await apiClient.post(`/courseware/${projectId}/synthesize`);
  return data;
}

export async function downloadCourseware(projectId: string): Promise<Blob> {
  const response = await apiClient.get(`/courseware/${projectId}/download`, { responseType: "blob" });
  return response.data;
}
