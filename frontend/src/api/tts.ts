import apiClient from "./client";
import type { TTSRequest, TTSResponse, VoiceResponse, ProviderCapabilities } from "../types";
export type { VoiceResponse } from "../types";

export async function synthesizeTTS(req: TTSRequest): Promise<TTSResponse> {
  const { data } = await apiClient.post<TTSResponse>("/tts/synthesize", req);
  return data;
}

export async function getVoices(): Promise<VoiceResponse[]> {
  const { data } = await apiClient.get<VoiceResponse[]>("/voices");
  return data;
}

export async function getCapabilities(): Promise<{
  providers: Array<{ provider: string; capabilities: ProviderCapabilities }>;
}> {
  const { data } = await apiClient.get("/capabilities");
  return data;
}
