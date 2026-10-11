import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';

export interface Issue {
  aspect: string | null;
  polarity: string;
  mentions: number;
  pct_negative: number;
  damage: number | null;
  priority_rank: number;
  confidence_label: string;
}

export interface SafetyAlert {
  review_id: string;
  clause_id: string;
  text: string;
  tier: string;
}

export interface AnalyzeResponse {
  analysis_id: string;
  filename: string;
  mode: string;
  review_count: number;
  avg_rating: number | null;
  pct_negative: number;
  rating_source?: string;
  languages: Record<string, number>;
  top_issues: Issue[];
  safety_alerts: SafetyAlert[];
  warnings: string[];
  processing_ms: number;
}

export interface Review {
  review_id: string;
  text: string;
  rating: number | null;
  lang: string;
  lang_tier: number;
  lang_confidence?: number;
  highlights: Array<{
    start: number;
    end: number;
    aspect: string | null;
    polarity: string;
    score: number;
  }>;
}

export interface ReviewsResponse {
  reviews: Review[];
}

export interface SimulationResponse {
  current_avg: number;
  projected_avg: number;
  contributions: Record<string, number>;
  single_cause_unhappy_count: number;
  confidence_labels: Record<string, string>;
  rating_source: string;
  caveat: string;
  estimate_label?: string | null;
}

export interface ActionEvidence {
  review_id: string;
  text: string;
  rating: number | null;
}

export interface ActionResponse {
  title: string;
  team: string;
  priority: string;
  summary: string;
  estimated_rating_uplift: number;
  evidence: ActionEvidence[];
  next_steps: string[];
  success_metric: string;
  reply_drafts: {
    english: string;
    hinglish: string;
  };
  ticket?: string;
  reply?: string;
}

export interface AnalysisListItem {
  id: string;
  filename: string;
  created_at: string;
  mode: string;
  review_count: number;
  avg_rating: number | null;
  rating_source?: string;
}

export interface ModelStatus {
  active: boolean;
  model_name: string;
  language: string;
  message: string;
}

export const api = {
  async health() {
    const res = await axios.get(`${API_URL}/health`);
    return res.data;
  },

  async modelStatus() {
    const res = await axios.get<ModelStatus>(`${API_URL}/api/model-status`);
    return res.data;
  },

  async analyze(file: File, mode?: string) {
    const formData = new FormData();
    formData.append('file', file);
    if (mode) {
      formData.append('mode', mode);
    }

    const res = await axios.post<AnalyzeResponse>(`${API_URL}/api/analyze`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  async listAnalyses() {
    const res = await axios.get<{ analyses: AnalysisListItem[] }>(`${API_URL}/api/analyses`);
    return res.data;
  },

  async getAnalysis(analysisId: string) {
    const res = await axios.get<AnalyzeResponse>(`${API_URL}/api/analyses/${analysisId}`);
    return res.data;
  },

  async getReviews(analysisId: string, aspect?: string, polarity?: string) {
    const params = new URLSearchParams();
    if (aspect) params.append('aspect', aspect);
    if (polarity) params.append('polarity', polarity);

    const res = await axios.get<ReviewsResponse>(
      `${API_URL}/api/analyses/${analysisId}/reviews?${params}`,
    );
    return res.data;
  },

  async simulate(analysisId: string, fixes: Record<string, number>) {
    const res = await axios.post<SimulationResponse>(`${API_URL}/api/analyses/${analysisId}/simulate`, { fixes });
    return res.data;
  },

  async generateActions(analysisId: string, aspect: string, polarity: string) {
    const res = await axios.post<ActionResponse>(`${API_URL}/api/analyses/${analysisId}/actions`, {
      aspect,
      polarity,
    });
    return res.data;
  },

  async deleteAnalysis(analysisId: string) {
    const res = await axios.delete<{ status: string }>(`${API_URL}/api/analyses/${analysisId}`);
    return res.data;
  },

  async exportAnalysis(analysisId: string, format: 'csv' | 'md' | 'markdown') {
    const normalized = format === 'markdown' ? 'md' : format;
    const res = await axios.get(`${API_URL}/api/analyses/${analysisId}/export`, {
      params: { format: normalized },
      responseType: 'blob',
    });
    return res.data as Blob;
  },
};
