import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import { IndexName, MapMode } from "@fieldmonitor/shared-types";

type State = {
  token: string;
  refreshToken: string;
  authEmail: string;
  setSession: (session: { accessToken: string; refreshToken: string; email: string }) => void;
  clearSession: () => void;
  selectedFieldId: string;
  setSelectedFieldId: (fieldId: string) => void;
  selectedIndex: IndexName;
  setSelectedIndex: (index: IndexName) => void;
  mapMode: MapMode;
  setMapMode: (mode: MapMode) => void;
  drawnGeometry: GeoJSON.Geometry | null;
  setDrawnGeometry: (geometry: GeoJSON.Geometry | null) => void;
  includeSrInAnalysis: boolean;
  setIncludeSrInAnalysis: (enabled: boolean) => void;
};

export const useAppStore = create<State>()(
  persist(
    (set) => ({
      token: "",
      refreshToken: "",
      authEmail: "",
      setSession: ({ accessToken, refreshToken, email }) =>
        set({ token: accessToken, refreshToken, authEmail: email.trim().toLowerCase() }),
      clearSession: () => set({ token: "", refreshToken: "", authEmail: "" }),
      selectedFieldId: "",
      setSelectedFieldId: (selectedFieldId) => set({ selectedFieldId }),
      selectedIndex: "NDVI",
      setSelectedIndex: (selectedIndex) => set({ selectedIndex }),
      mapMode: "NATIVE",
      setMapMode: (mapMode) => set({ mapMode }),
      drawnGeometry: null,
      setDrawnGeometry: (drawnGeometry) => set({ drawnGeometry }),
      includeSrInAnalysis: true,
      setIncludeSrInAnalysis: (includeSrInAnalysis) => set({ includeSrInAnalysis }),
    }),
    {
      name: "fieldmonitor-session-v1",
      partialize: (state) => ({
        token: state.token,
        refreshToken: state.refreshToken,
        authEmail: state.authEmail,
      }),
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
