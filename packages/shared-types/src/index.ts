export type IndexName = "NDVI" | "NDMI" | "NDWI" | "EVI" | "NDRE" | "SAVI";

export type MapMode = "NATIVE" | "SR" | "SIDE_BY_SIDE" | "SWIPE";

export interface FieldSummary {
  id: string;
  farm_id: string;
  name: string;
  area_ha: number;
  geometry: GeoJSON.Geometry;
  schedule?: {
    enabled?: boolean;
    timezone?: string;
    local_time?: string;
    frequency?: "daily" | "weekly";
  };
}

export interface AnalysisPoint {
  id: string;
  observed_on: string;
  status: string;
  cloud_cover?: number;
  valid_pixel_ratio?: number;
  indices_native: Record<string, unknown>;
  indices_sr: Record<string, unknown>;
}

export interface AlertItem {
  id: string;
  organization_id: string;
  field_id?: string;
  severity: string;
  category: string;
  message: string;
  acknowledged_at?: string;
  metadata_json: Record<string, unknown>;
}
