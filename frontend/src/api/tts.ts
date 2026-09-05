import apiClient from "./client";
import type { TTSRequest, TTSResponse, VoiceResponse, ProviderCapabilities, CloneResponse, TTSHistoryItem } from "../types";
export type { VoiceResponse } from "../types";

export async function synthesizeTTS(req: TTSRequest): Promise<TTSResponse> {
  const { data } = await apiClient.post<TTSResponse>("/tts/synthesize", req);
  return data;
}

export async function getVoices(): Promise<VoiceResponse[]> {
  const { data } = await apiClient.get<VoiceResponse[]>("/voices");
  return data;
}

export async function getHistory(): Promise<TTSHistoryItem[]> {
  const { data } = await apiClient.get<TTSHistoryItem[]>("/tts/history");
  return data;
}

export async function cloneVoice(input: {
  file: File;
  name: string;
  purpose: string;
  description?: string;
}): Promise<CloneResponse> {
  const form = new FormData();
  form.append("file", input.file);
  form.append("name", input.name);
  form.append("purpose", input.purpose);
  if (input.description) form.append("description", input.description);
  const { data } = await apiClient.post<CloneResponse>("/voices/clone", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getCapabilities(): Promise<{
  providers: Array<{ provider: string; capabilities: ProviderCapabilities }>;
}> {
  const { data } = await apiClient.get("/capabilities");
  return data;
}
