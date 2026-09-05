export interface ProviderCapabilities {
  max_text_length: number;
  supported_formats: string[];
  streaming: boolean;
  emotions: string[];
  styles: string[];
  languages: string[];
  instruct_mode: boolean;
  zero_shot_clone: boolean;
  clone_min_duration: number;
  clone_max_duration: number;
}

export interface TTSRequest {
  text: string;
  voice_id: string;
  speed?: number;
  pitch?: number;
  volume?: number;
  emotion?: string | null;
  style?: string | null;
  language?: string;
  instruction?: string | null;
  output_format?: string;
}

export interface TTSResponse {
  task_id: string;
  status: string;
  audio_url: string | null;
  cached: boolean;
  provider_used: string | null;
  duration_ms: number | null;
  processed_text: string | null;
}

export interface VoiceResponse {
  id: string;
  name: string;
  type: string;
  provider: string;
  is_public: boolean;
  description: string | null;
}

export interface CloneResponse {
  status: string;
  voice_id: string | null;
  voice_meta: { id: string; name: string } | null;
  message: string | null;
  error: string | null;
}

export interface TTSHistoryItem {
  id: string;
  text: string;
  audio_url: string | null;
  created_at: string | null;
  provider: string | null;
}

export interface UserInfo {
  id: string;
  email: string;
  username: string;
  role: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
