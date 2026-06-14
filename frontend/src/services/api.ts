import axios from "axios";
import type { Call, CallsQueryParams, PaginatedCallsResponse } from "@/types/calls";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api`,
  headers: {
    "Content-Type": "application/json",
  },
});

export const callsApi = {
  list: async (params: CallsQueryParams): Promise<PaginatedCallsResponse> => {
    const { data } = await apiClient.get<PaginatedCallsResponse>("/calls", { params });
    return data;
  },

  getById: async (id: string): Promise<Call> => {
    const { data } = await apiClient.get<Call>(`/calls/${id}`);
    return data;
  },

  updateNotes: async (id: string, notes: string | null): Promise<Call> => {
    const { data } = await apiClient.patch<Call>(`/calls/${id}/notes`, { notes });
    return data;
  },
};
