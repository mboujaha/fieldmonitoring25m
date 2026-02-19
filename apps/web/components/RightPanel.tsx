"use client";

import { useEffect, useState } from "react";
import { AnalysisPoint, AlertItem, FieldSummary, IndexName } from "@fieldmonitor/shared-types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHint, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { AnalysisJob, ExportJob, ImageryItem } from "@/lib/api";
import { cn } from "@/lib/utils";

interface RightPanelProps {
  isAuthenticated: boolean;
  fields: FieldSummary[];
  selectedFieldId: string;
  onFieldChange: (id: string) => void;
  points: AnalysisPoint[];
  alerts: AlertItem[];
  imageryResults: ImageryItem[];
  selectedSceneId: string;
  onSceneSelect: (sceneId: string) => void;
  selectedIndex: IndexName;
  onAckAlert: (alertId: string) => Promise<void>;
  onClearTimeline: () => Promise<void>;
  onClearAlerts: () => Promise<void>;
  onCreateExport: (format: "CSV" | "PNG" | "GEOTIFF") => Promise<void>;
  latestAnalysis: AnalysisJob | null;
  isAnalysisPolling: boolean;
  latestExport: ExportJob | null;
  onUpdateSchedule: (payload: {
    enabled: boolean;
    timezone: string;
    local_time: string;
    frequency: "daily" | "weekly";
  }) => Promise<void>;
  isExporting: boolean;
  isExportPolling: boolean;
  isAcknowledgingAlert: boolean;
  isClearingTimeline: boolean;
  isClearingAlerts: boolean;
  isUpdatingSchedule: boolean;
}

function severityVariant(severity: string): "soft" | "warn" | "danger" | "success" {
  if (severity === "CRITICAL") return "danger";
  if (severity === "WARN") return "warn";
  if (severity === "INFO") return "soft";
  return "success";
}

function statusVariant(status: string): "soft" | "warn" | "danger" | "success" {
  if (status === "FAILED") return "danger";
  if (status === "LOW_QUALITY_SKIPPED") return "warn";
  if (status === "SUCCEEDED") return "success";
  return "soft";
}

export function RightPanel({
  isAuthenticated,
  fields = [],
  selectedFieldId,
  onFieldChange,
  points,
  alerts,
  imageryResults = [],
  selectedSceneId = "",
  onSceneSelect,
  selectedIndex,
  onAckAlert,
  onClearTimeline,
  onClearAlerts,
  onCreateExport,
  latestAnalysis,
  isAnalysisPolling,
  latestExport,
  onUpdateSchedule,
  isExporting,
  isExportPolling,
  isAcknowledgingAlert,
  isClearingTimeline,
  isClearingAlerts,
  isUpdatingSchedule,
}: RightPanelProps) {
  const safeFields = Array.isArray(fields) ? fields : [];
  const safeImagery = Array.isArray(imageryResults) ? imageryResults : [];
  const latestPoint = points[points.length - 1];
  const selectedField = safeFields.find((field) => field.id === selectedFieldId);
  const [scheduleEnabled, setScheduleEnabled] = useState(true);
  const [scheduleTimezone, setScheduleTimezone] = useState("UTC");
  const [scheduleLocalTime, setScheduleLocalTime] = useState("06:00");
  const [scheduleFrequency, setScheduleFrequency] = useState<"daily" | "weekly">("daily");

  const analysisResult =
    latestAnalysis?.result_json && typeof latestAnalysis.result_json === "object" && !Array.isArray(latestAnalysis.result_json)
      ? latestAnalysis.result_json
      : null;

  useEffect(() => {
    if (!selectedField?.schedule) {
      return;
    }
    setScheduleEnabled(selectedField.schedule.enabled ?? true);
    setScheduleTimezone(selectedField.schedule.timezone ?? "UTC");
    setScheduleLocalTime(selectedField.schedule.local_time ?? "06:00");
    setScheduleFrequency((selectedField.schedule.frequency as "daily" | "weekly") ?? "daily");
  }, [selectedField?.id, selectedField?.schedule]);

  const invoke = async (task: () => Promise<void>) => {
    try {
      await task();
    } catch {
      // status messages are handled by parent mutations
    }
  };

  return (
    <aside className="panel-scroll ui-panel animate-panel flex h-full w-full flex-col gap-4 overflow-y-auto p-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold tracking-tight text-[var(--ink-800)]">Insights</h2>
          <p className="text-xs text-[var(--ink-600)]">Timeline, exports, and alert operations.</p>
        </div>
        <Badge variant="soft">{selectedIndex}</Badge>
      </div>

      {!isAuthenticated && (
        <Card>
          <CardHint>Sign in from the left panel to load timeline data, alerts, and exports.</CardHint>
        </Card>
      )}

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <CardTitle>Imagery Results</CardTitle>
          <Badge variant="soft">{safeImagery.length} scenes</Badge>
        </div>
        <CardHint className="mb-3">
          These are catalog search results. Only selected scene footprints are shown on the map.
        </CardHint>
        <div className="max-h-72 space-y-2 overflow-auto pr-1">
          {safeImagery.length === 0 && <CardHint>Run "Search Imagery" to populate this list.</CardHint>}
          {safeImagery.map((scene) => {
            const isSelected = scene.scene_id === selectedSceneId;
            return (
              <button
                key={scene.scene_id}
                type="button"
                onClick={() => onSceneSelect(isSelected ? "" : scene.scene_id)}
                className={cn(
                  "w-full rounded-lg border px-2 py-2 text-left transition",
                  isSelected
                    ? "border-[var(--accent-400)] bg-[var(--accent-100)]/60"
                    : "border-[var(--line)] bg-[var(--surface-1)] hover:bg-[var(--surface-2)]",
                )}
                title={scene.scene_id}
              >
                <div className="mb-2 grid grid-cols-[72px_minmax(0,1fr)] gap-2">
                  <div className="h-[54px] w-[72px] overflow-hidden rounded-md border border-[var(--line)] bg-[var(--surface-1)]">
                    {scene.preview_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={scene.preview_url}
                        alt={scene.scene_id}
                        className="h-full w-full object-cover"
                        loading="lazy"
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center text-[10px] text-[var(--ink-400)]">No preview</div>
                    )}
                  </div>
                  <div className="min-w-0 text-xs text-[var(--ink-600)]">
                    <div className="truncate font-semibold text-[var(--ink-800)]">{scene.scene_id}</div>
                    <div>{new Date(scene.acquisition_date).toLocaleDateString()}</div>
                    <div>Cloud: {scene.cloud_cover ?? "-"}%</div>
                    <div>
                      Coverage:{" "}
                      {typeof scene.field_coverage_ratio === "number"
                        ? `${Math.round(scene.field_coverage_ratio * 100)}%`
                        : "-"}
                    </div>
                  </div>
                </div>
                <div className="flex items-center justify-between text-[11px] text-[var(--ink-500)]">
                  <span>{scene.collection}</span>
                  <Badge variant={isSelected ? "success" : "soft"}>{isSelected ? "Selected" : "Scene"}</Badge>
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      <Card>
        <CardTitle>Field Focus</CardTitle>
        <CardHint className="mb-3 mt-1">Select a field to load timeline, imagery, alerts, and exports.</CardHint>
        <select
          className="h-10 w-full rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 text-sm text-[var(--ink-800)] outline-none transition focus:border-[var(--accent-400)] focus:ring-2 focus:ring-[var(--accent-200)]"
          value={selectedFieldId}
          onChange={(event) => onFieldChange(event.target.value)}
          disabled={!isAuthenticated || safeFields.length === 0}
        >
          {safeFields.length === 0 ? (
            <option value="">No fields yet</option>
          ) : (
            safeFields.map((field) => (
              <option key={field.id} value={field.id}>
                {field.name}
              </option>
            ))
          )}
        </select>
        {selectedField && (
          <div className="mt-3 rounded-md border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2 text-xs text-[var(--ink-600)]">
            <div className="font-semibold text-[var(--ink-800)]">{selectedField.name}</div>
            <div>Area: {selectedField.area_ha.toFixed(2)} ha</div>
            <div className="truncate">Field ID: {selectedField.id}</div>
          </div>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <CardTitle>Schedule</CardTitle>
          <Badge variant={scheduleEnabled ? "success" : "warn"}>{scheduleEnabled ? "Enabled" : "Disabled"}</Badge>
        </div>
        <CardHint className="mb-3">Per-field automatic monitoring schedule.</CardHint>
        <div className="space-y-2 text-xs">
          <label className="flex items-center justify-between rounded-md border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2">
            <span className="text-[var(--ink-700)]">Auto run</span>
            <Switch
              checked={scheduleEnabled}
              onCheckedChange={setScheduleEnabled}
              disabled={!selectedField || !isAuthenticated || isUpdatingSchedule}
            />
          </label>
          <Input
            value={scheduleTimezone}
            onChange={(event) => setScheduleTimezone(event.target.value)}
            placeholder="Timezone (e.g. UTC, Europe/Paris)"
            disabled={!selectedField || !isAuthenticated || isUpdatingSchedule}
          />
          <Input
            type="time"
            value={scheduleLocalTime}
            onChange={(event) => setScheduleLocalTime(event.target.value)}
            disabled={!selectedField || !isAuthenticated || isUpdatingSchedule}
          />
          <select
            className="h-9 w-full rounded-md border border-[var(--line)] bg-[var(--surface-1)] px-2 text-[var(--ink-800)]"
            value={scheduleFrequency}
            onChange={(event) => setScheduleFrequency(event.target.value as "daily" | "weekly")}
            disabled={!selectedField || !isAuthenticated || isUpdatingSchedule}
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly (Monday)</option>
          </select>
          <Button
            size="sm"
            className="w-full"
            disabled={!selectedField || !isAuthenticated || isUpdatingSchedule}
            onClick={() =>
              void invoke(() =>
                onUpdateSchedule({
                  enabled: scheduleEnabled,
                  timezone: scheduleTimezone,
                  local_time: scheduleLocalTime,
                  frequency: scheduleFrequency,
                }),
              )
            }
          >
            {isUpdatingSchedule ? "Saving..." : "Save Schedule"}
          </Button>
        </div>
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <CardTitle>Latest Analysis</CardTitle>
          <Badge variant={latestAnalysis ? statusVariant(latestAnalysis.status) : "soft"}>
            {latestAnalysis ? latestAnalysis.status.replaceAll("_", " ") : "No job"}
          </Badge>
        </div>
        {!latestAnalysis ? (
          <CardHint>Run analysis to track progress and result details here.</CardHint>
        ) : (
          <div className="space-y-2 text-xs text-[var(--ink-600)]">
            <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2">
              <div className="text-[10px] uppercase tracking-wide text-[var(--ink-400)]">Job ID</div>
              <div className="mt-1 truncate font-semibold text-[var(--ink-800)]">{latestAnalysis.id}</div>
            </div>
            {analysisResult && (
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2">
                  <div className="text-[10px] uppercase tracking-wide text-[var(--ink-400)]">Scene</div>
                  <div className="mt-1 truncate font-semibold text-[var(--ink-800)]">
                    {typeof analysisResult.scene_id === "string" ? analysisResult.scene_id : "-"}
                  </div>
                </div>
                <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2">
                  <div className="text-[10px] uppercase tracking-wide text-[var(--ink-400)]">Cloud</div>
                  <div className="mt-1 font-semibold text-[var(--ink-800)]">
                    {typeof analysisResult.cloud_cover === "number" ? `${analysisResult.cloud_cover.toFixed(2)}%` : "-"}
                  </div>
                </div>
                <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2">
                  <div className="text-[10px] uppercase tracking-wide text-[var(--ink-400)]">Valid Pixels</div>
                  <div className="mt-1 font-semibold text-[var(--ink-800)]">
                    {typeof analysisResult.valid_pixel_ratio === "number"
                      ? `${(analysisResult.valid_pixel_ratio * 100).toFixed(1)}%`
                      : "-"}
                  </div>
                </div>
                <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2">
                  <div className="text-[10px] uppercase tracking-wide text-[var(--ink-400)]">Reason</div>
                  <div className="mt-1 truncate font-semibold text-[var(--ink-800)]">
                    {typeof analysisResult.reason === "string"
                      ? analysisResult.reason.replaceAll("_", " ")
                      : typeof analysisResult.status === "string"
                        ? analysisResult.status.replaceAll("_", " ")
                        : "-"}
                  </div>
                </div>
                <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2">
                  <div className="text-[10px] uppercase tracking-wide text-[var(--ink-400)]">SR Requested</div>
                  <div className="mt-1 font-semibold text-[var(--ink-800)]">
                    {typeof analysisResult.sr_requested === "boolean" ? (analysisResult.sr_requested ? "Yes" : "No") : "-"}
                  </div>
                </div>
                <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2">
                  <div className="text-[10px] uppercase tracking-wide text-[var(--ink-400)]">SR Layer Produced</div>
                  <div className="mt-1 font-semibold text-[var(--ink-800)]">
                    {typeof analysisResult.sr_visualization_generated === "boolean"
                      ? (analysisResult.sr_visualization_generated ? "Yes" : "No")
                      : "-"}
                  </div>
                </div>
              </div>
            )}
            {latestAnalysis.status === "FAILED" && latestAnalysis.error_message && (
              <CardHint className="rounded-md border border-[var(--warn-300)] bg-[var(--warn-100)] px-2 py-1 text-[var(--warn-700)]">
                {latestAnalysis.error_message}
              </CardHint>
            )}
            {analysisResult && typeof analysisResult.sr_error === "string" && analysisResult.sr_error.trim() && (
              <CardHint className="rounded-md border border-[var(--warn-300)] bg-[var(--warn-100)] px-2 py-1 text-[var(--warn-700)]">
                SR error: {analysisResult.sr_error}
              </CardHint>
            )}
            {(latestAnalysis.status === "QUEUED" || latestAnalysis.status === "RUNNING") && (
              <CardHint>{isAnalysisPolling ? "Refreshing analysis status..." : "Waiting for worker update..."}</CardHint>
            )}
          </div>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <CardTitle>Latest Snapshot</CardTitle>
          <Badge variant={latestPoint ? statusVariant(latestPoint.status) : "soft"}>
            {latestPoint ? latestPoint.status.replaceAll("_", " ") : "No data"}
          </Badge>
        </div>
        {latestPoint ? (
          <div className="grid grid-cols-2 gap-2 text-xs text-[var(--ink-600)]">
            <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2">
              <div className="text-[10px] uppercase tracking-wide text-[var(--ink-400)]">Date</div>
              <div className="mt-1 font-semibold text-[var(--ink-800)]">{latestPoint.observed_on}</div>
            </div>
            <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2">
              <div className="text-[10px] uppercase tracking-wide text-[var(--ink-400)]">Cloud</div>
              <div className="mt-1 font-semibold text-[var(--ink-800)]">{latestPoint.cloud_cover ?? "-"}%</div>
            </div>
            <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2">
              <div className="text-[10px] uppercase tracking-wide text-[var(--ink-400)]">Valid Pixels</div>
              <div className="mt-1 font-semibold text-[var(--ink-800)]">{latestPoint.valid_pixel_ratio ?? "-"}</div>
            </div>
            <div className="rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2">
              <div className="text-[10px] uppercase tracking-wide text-[var(--ink-400)]">Observations</div>
              <div className="mt-1 font-semibold text-[var(--ink-800)]">{points.length}</div>
            </div>
          </div>
        ) : (
          <CardHint>No observations available yet. Run analysis to populate this panel.</CardHint>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <CardTitle>Timeline ({selectedIndex})</CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="soft">{points.length} points</Badge>
            <Button
              variant="outline"
              size="sm"
              disabled={!isAuthenticated || !selectedFieldId || points.length === 0 || isClearingTimeline}
              onClick={() => {
                if (typeof window !== "undefined") {
                  const confirmed = window.confirm("Clear all timeline observations for this field?");
                  if (!confirmed) return;
                }
                void invoke(onClearTimeline);
              }}
            >
              {isClearingTimeline ? "Clearing..." : "Clear"}
            </Button>
          </div>
        </div>
        <div className="max-h-72 space-y-2 overflow-auto pr-1">
          {points.length === 0 && <CardHint>No observations yet.</CardHint>}
          {points.map((point) => {
            const nativeMean = (point.indices_native[selectedIndex] as { stats?: { mean?: number } } | undefined)?.stats?.mean;
            const srMean = (point.indices_sr[selectedIndex] as { stats?: { mean?: number } } | undefined)?.stats?.mean;
            return (
              <div
                key={point.id}
                className="rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2 text-xs"
              >
                <div className="mb-1 flex items-center justify-between">
                  <span className="font-semibold text-[var(--ink-800)]">{point.observed_on}</span>
                  <Badge variant={statusVariant(point.status)}>{point.status.replaceAll("_", " ")}</Badge>
                </div>
                <div className="grid grid-cols-2 gap-1 text-[var(--ink-500)]">
                  <div>Cloud: {point.cloud_cover ?? "-"}%</div>
                  <div>Valid: {point.valid_pixel_ratio ?? "-"}</div>
                  <div>Native mean: {nativeMean ?? "N/A"}</div>
                  <div>SR mean: {srMean ?? "N/A"}</div>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <Card>
        <CardTitle>Exports</CardTitle>
        <CardHint className="mb-3 mt-1">Generate outputs for GIS and reporting workflows.</CardHint>
        <div className="grid grid-cols-3 gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!isAuthenticated || !selectedFieldId || isExporting}
            onClick={() => void invoke(() => onCreateExport("CSV"))}
          >
            CSV
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!isAuthenticated || !selectedFieldId || isExporting}
            onClick={() => void invoke(() => onCreateExport("PNG"))}
          >
            PNG
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!isAuthenticated || !selectedFieldId || isExporting}
            onClick={() => void invoke(() => onCreateExport("GEOTIFF"))}
          >
            GeoTIFF
          </Button>
        </div>
        {latestExport && (
          <div className="mt-3 rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2 text-xs text-[var(--ink-600)]">
            <div className="mb-1 flex items-center justify-between">
              <span className="font-semibold text-[var(--ink-800)]">Latest job</span>
              <Badge variant={statusVariant(latestExport.status)}>{latestExport.status.replaceAll("_", " ")}</Badge>
            </div>
            <div className="truncate text-[10px] text-[var(--ink-500)]">{latestExport.id}</div>
            {latestExport.output_uri ? (
              <a
                className="mt-2 inline-flex h-8 items-center rounded-md border border-[var(--line-strong)] bg-[var(--surface-2)] px-3 font-semibold text-[var(--ink-800)] transition hover:border-[var(--accent-400)] hover:bg-[var(--accent-100)]"
                href={latestExport.output_uri}
                target="_blank"
                rel="noreferrer"
              >
                Download latest export
              </a>
            ) : (
              <CardHint className="mt-2">
                {isExportPolling ? "Preparing export artifact..." : "Artifact URL not ready yet."}
              </CardHint>
            )}
            {latestExport.status === "FAILED" && latestExport.error_message && (
              <CardHint className="mt-2 rounded-md border border-[var(--warn-300)] bg-[var(--warn-100)] px-2 py-1 text-[var(--warn-700)]">
                {latestExport.error_message}
              </CardHint>
            )}
          </div>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <CardTitle>Alerts</CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="soft">{alerts.filter((item) => !item.acknowledged_at).length} open</Badge>
            <Button
              variant="outline"
              size="sm"
              disabled={!isAuthenticated || alerts.length === 0 || isClearingAlerts}
              onClick={() => {
                if (typeof window !== "undefined") {
                  const confirmed = window.confirm("Clear all alerts?");
                  if (!confirmed) return;
                }
                void invoke(onClearAlerts);
              }}
            >
              {isClearingAlerts ? "Clearing..." : "Clear"}
            </Button>
          </div>
        </div>
        <div className="max-h-80 space-y-2 overflow-auto pr-1">
          {alerts.length === 0 && <CardHint>No alerts for this session.</CardHint>}
          {alerts.map((alert) => (
            <div key={alert.id} className="rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2 text-xs">
              <div className="mb-1 flex items-center justify-between gap-2">
                <Badge variant={severityVariant(alert.severity)}>{alert.severity}</Badge>
                <span className="truncate font-semibold text-[var(--ink-800)]">{alert.category}</span>
              </div>
              <p className="text-[var(--ink-700)]">{alert.message}</p>
              <div className="mt-2 flex items-center justify-between">
                <span className="text-[var(--ink-500)]">{alert.acknowledged_at ? "Acknowledged" : "Pending"}</span>
                {!alert.acknowledged_at && isAuthenticated && (
                  <Button
                    size="sm"
                    disabled={isAcknowledgingAlert}
                    onClick={() => void invoke(() => onAckAlert(alert.id))}
                  >
                    Acknowledge
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </aside>
  );
}
