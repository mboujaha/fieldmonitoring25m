"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { LeftPanel } from "@/components/LeftPanel";
import { MapWorkspace } from "@/components/MapWorkspace";
import { RightPanel } from "@/components/RightPanel";
import { Badge } from "@/components/ui/badge";
import {
  ackAlert,
  clearAlerts,
  clearFieldTimeline,
  createFarm,
  createExport,
  createField,
  createOrganization,
  getAnalysisJob,
  getExportJob,
  getTimeseries,
  ImageryItem,
  importField,
  listFields,
  loginAuth,
  listFarms,
  listAlerts,
  registerAuth,
  searchImagery,
  startAnalysis,
  updateFieldSchedule,
} from "@/lib/api";
import { computeGeometryAreaHa } from "@/lib/geo";
import { useAppStore } from "@/store/useAppStore";

function errorToMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Unexpected error";
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function formatAnalysisSuccessMessage(jobId: string, result: Record<string, unknown> | null): string {
  if (!result) {
    return `Analysis completed: ${jobId}`;
  }

  const sceneId = typeof result.scene_id === "string" ? result.scene_id : null;
  const cloudCover = typeof result.cloud_cover === "number" ? result.cloud_cover : null;
  const validPixelRatio = typeof result.valid_pixel_ratio === "number" ? result.valid_pixel_ratio : null;
  const nativeIndices = Array.isArray(result.native_indices) ? result.native_indices.length : null;
  const srIndices = Array.isArray(result.sr_indices) ? result.sr_indices.length : null;

  const details: string[] = [];
  if (sceneId) details.push(`scene ${sceneId}`);
  if (cloudCover !== null) details.push(`cloud ${cloudCover.toFixed(2)}%`);
  if (validPixelRatio !== null) details.push(`valid ${(validPixelRatio * 100).toFixed(1)}%`);
  if (nativeIndices !== null) details.push(`native idx ${nativeIndices}`);
  if (srIndices !== null) details.push(`sr idx ${srIndices}`);

  if (details.length === 0) {
    return `Analysis completed: ${jobId}`;
  }
  return `Analysis completed: ${details.join(" • ")}`;
}

function formatAnalysisSkippedMessage(jobId: string, result: Record<string, unknown> | null): string {
  if (!result) {
    return `Analysis skipped: ${jobId}`;
  }

  const reason = typeof result.reason === "string" ? result.reason : typeof result.status === "string" ? result.status : null;
  const sceneId = typeof result.scene_id === "string" ? result.scene_id : null;
  const details: string[] = [];
  if (reason) details.push(reason.replaceAll("_", " "));
  if (sceneId) details.push(`scene ${sceneId}`);
  if (typeof result.cloud_cover === "number") details.push(`cloud ${result.cloud_cover.toFixed(2)}%`);
  if (typeof result.valid_pixel_ratio === "number") details.push(`valid ${(result.valid_pixel_ratio * 100).toFixed(1)}%`);

  if (details.length === 0) {
    return `Analysis skipped: ${jobId}`;
  }
  return `Analysis skipped: ${details.join(" • ")}`;
}

export default function HomePage() {
  const queryClient = useQueryClient();
  const [statusMessage, setStatusMessage] = useState<string>("Ready");
  const [selectedFarmId, setSelectedFarmId] = useState<string>("");
  const [imageryResults, setImageryResults] = useState<ImageryItem[]>([]);
  const [selectedSceneId, setSelectedSceneId] = useState<string>("");
  const [latestAnalysisId, setLatestAnalysisId] = useState<string>("");
  const [latestExportId, setLatestExportId] = useState<string>("");
  const latestAnalysisStatusRef = useRef<string>("");
  const latestExportStatusRef = useRef<string>("");

  const {
    token,
    authEmail,
    setSession,
    clearSession,
    selectedFieldId,
    setSelectedFieldId,
    selectedIndex,
    setSelectedIndex,
    mapMode,
    setMapMode,
    drawnGeometry,
    setDrawnGeometry,
    includeSrInAnalysis,
    setIncludeSrInAnalysis,
  } = useAppStore();
  const isAuthenticated = Boolean(token);

  const handleAuthFailure = (error: unknown, fallback: string) => {
    const message = errorToMessage(error);
    const lowered = message.toLowerCase();
    if (lowered.includes("401") || lowered.includes("not authenticated") || lowered.includes("invalid credentials")) {
      clearSession();
      setStatusMessage("Session expired or invalid. Please sign in.");
      return;
    }
    setStatusMessage(fallback);
  };

  const loginMutation = useMutation({
    mutationFn: (payload: { email: string; password: string }) => loginAuth(payload),
    onSuccess: (tokens, payload) => {
      setSession({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        email: payload.email,
      });
      setStatusMessage("Signed in successfully.");
    },
    onError: (error) => {
      setStatusMessage(`Sign in failed: ${errorToMessage(error)}`);
    },
  });

  const registerMutation = useMutation({
    mutationFn: (payload: { email: string; password: string; fullName?: string }) =>
      registerAuth({
        email: payload.email,
        password: payload.password,
        full_name: payload.fullName,
      }),
    onSuccess: (tokens, payload) => {
      setSession({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
        email: payload.email,
      });
      setStatusMessage("Account created and signed in.");
    },
    onError: (error) => {
      setStatusMessage(`Registration failed: ${errorToMessage(error)}`);
    },
  });

  const timeseriesQuery = useQuery({
    queryKey: ["timeseries", selectedFieldId, selectedIndex, token],
    queryFn: () => getTimeseries(selectedFieldId, selectedIndex, token),
    enabled: Boolean(token && selectedFieldId),
  });

  const alertsQuery = useQuery({
    queryKey: ["alerts", token],
    queryFn: () => listAlerts(token),
    enabled: Boolean(token),
    refetchInterval: 30_000,
    retry: false,
  });

  const farmsQuery = useQuery({
    queryKey: ["farms", token],
    queryFn: () => listFarms(token),
    enabled: Boolean(token),
    retry: false,
  });

  const fieldsQuery = useQuery({
    queryKey: ["fields", selectedFarmId, token],
    queryFn: () => listFields({ farm_id: selectedFarmId }, token),
    enabled: Boolean(token && selectedFarmId),
    retry: false,
  });

  const exportStatusQuery = useQuery({
    queryKey: ["export-job", latestExportId, token],
    queryFn: () => getExportJob(latestExportId, token),
    enabled: Boolean(token && latestExportId),
    retry: false,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "QUEUED" || status === "RUNNING") {
        return 2_000;
      }
      return false;
    },
  });

  const analysisStatusQuery = useQuery({
    queryKey: ["analysis-job", selectedFieldId, latestAnalysisId, token],
    queryFn: () => getAnalysisJob(selectedFieldId, latestAnalysisId, token),
    enabled: Boolean(token && selectedFieldId && latestAnalysisId),
    retry: false,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "QUEUED" || status === "RUNNING") {
        return 2_000;
      }
      return false;
    },
  });

  const createFieldMutation = useMutation({
    mutationFn: (payload: { farmId: string; name: string }) => {
      if (!drawnGeometry) {
        throw new Error("Draw a polygon first.");
      }
      return createField({ farm_id: payload.farmId, name: payload.name, geometry: drawnGeometry }, token);
    },
    onSuccess: (field) => {
      setSelectedFieldId(field.id);
      setStatusMessage(`Field created: ${field.name}`);
      queryClient.invalidateQueries({ queryKey: ["fields", selectedFarmId, token] });
    },
    onError: (error) => {
      handleAuthFailure(error, `Field creation failed: ${errorToMessage(error)}`);
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (payload: { farmId: string; name: string; file: File }) =>
      importField({ farm_id: payload.farmId, name: payload.name, file: payload.file }, token),
    onSuccess: (field) => {
      setSelectedFieldId(field.id);
      setStatusMessage(`Field uploaded: ${field.name}`);
      queryClient.invalidateQueries({ queryKey: ["fields", selectedFarmId, token] });
    },
    onError: (error) => {
      handleAuthFailure(error, `Upload failed: ${errorToMessage(error)}`);
    },
  });

  const imageryMutation = useMutation({
    mutationFn: (payload: { dateFrom?: string; dateTo?: string; maxCloud?: number }) =>
      searchImagery(
        selectedFieldId,
        { date_from: payload.dateFrom, date_to: payload.dateTo, max_cloud: payload.maxCloud },
        token,
      ),
    onSuccess: (items) => {
      setImageryResults(items);
      setSelectedSceneId(items[0]?.scene_id ?? "");
      setStatusMessage(
        `Imagery search returned ${items.length} scene(s). Select a scene to show its footprint on the map.`,
      );
    },
    onError: (error) => {
      handleAuthFailure(error, `Imagery search failed: ${errorToMessage(error)}`);
    },
  });

  const analysisMutation = useMutation({
    mutationFn: (payload: {
      sceneId?: string;
      dateFrom?: string;
      dateTo?: string;
      maxCloud?: number;
      includeSr: boolean;
    }) =>
      startAnalysis(
        selectedFieldId,
        {
          scene_id: payload.sceneId,
          date_from: payload.dateFrom,
          date_to: payload.dateTo,
          max_cloud: payload.maxCloud,
          include_sr: payload.includeSr,
          include_radar_overlay: true,
        },
        token,
      ),
    onSuccess: (job) => {
      setLatestAnalysisId(job.id);
      latestAnalysisStatusRef.current = "";
      setStatusMessage(`Analysis queued: ${job.id}`);
    },
    onError: (error) => {
      handleAuthFailure(error, `Analysis queue failed: ${errorToMessage(error)}`);
    },
  });

  const ackAlertMutation = useMutation({
    mutationFn: (alertId: string) => ackAlert(alertId, token),
    onSuccess: () => {
      setStatusMessage("Alert acknowledged.");
      queryClient.invalidateQueries({ queryKey: ["alerts", token] });
    },
    onError: (error) => {
      handleAuthFailure(error, `Alert acknowledgement failed: ${errorToMessage(error)}`);
    },
  });

  const clearTimelineMutation = useMutation({
    mutationFn: () => clearFieldTimeline(selectedFieldId, token),
    onSuccess: (result) => {
      setStatusMessage(`Timeline cleared (${result.deleted_total} records).`);
      setImageryResults([]);
      setSelectedSceneId("");
      queryClient.invalidateQueries({ queryKey: ["timeseries", selectedFieldId, selectedIndex, token] });
    },
    onError: (error) => {
      handleAuthFailure(error, `Timeline clear failed: ${errorToMessage(error)}`);
    },
  });

  const clearAlertsMutation = useMutation({
    mutationFn: () => clearAlerts(token),
    onSuccess: (result) => {
      setStatusMessage(`Alerts cleared (${result.deleted_alerts}).`);
      queryClient.invalidateQueries({ queryKey: ["alerts", token] });
    },
    onError: (error) => {
      handleAuthFailure(error, `Alerts clear failed: ${errorToMessage(error)}`);
    },
  });

  const exportMutation = useMutation({
    mutationFn: (format: "CSV" | "PNG" | "GEOTIFF") =>
      createExport(
        {
          field_id: selectedFieldId,
          format,
          index_name: selectedIndex,
          source_mode: mapMode === "NATIVE" ? "native" : "sr",
        },
        token,
      ),
    onSuccess: (exportJob) => {
      setLatestExportId(exportJob.id);
      latestExportStatusRef.current = "";
      setStatusMessage(`Export queued: ${exportJob.id}`);
    },
    onError: (error) => {
      handleAuthFailure(error, `Export failed: ${errorToMessage(error)}`);
    },
  });

  const scheduleMutation = useMutation({
    mutationFn: (payload: {
      enabled: boolean;
      timezone: string;
      local_time: string;
      frequency: "daily" | "weekly";
    }) => updateFieldSchedule(selectedFieldId, payload, token),
    onSuccess: async () => {
      setStatusMessage("Field schedule saved.");
      await queryClient.invalidateQueries({ queryKey: ["fields", selectedFarmId, token] });
    },
    onError: (error) => {
      handleAuthFailure(error, `Schedule update failed: ${errorToMessage(error)}`);
    },
  });

  const points = useMemo(() => timeseriesQuery.data?.points ?? [], [timeseriesQuery.data]);
  const alerts = useMemo(() => alertsQuery.data ?? [], [alertsQuery.data]);
  const farms = useMemo(() => farmsQuery.data ?? [], [farmsQuery.data]);
  const fields = useMemo(() => fieldsQuery.data ?? [], [fieldsQuery.data]);
  const selectedFieldGeometry = useMemo(
    () => fields.find((field) => field.id === selectedFieldId)?.geometry ?? null,
    [fields, selectedFieldId],
  );
  const drawnAreaHa = useMemo(
    () => (drawnGeometry ? computeGeometryAreaHa(drawnGeometry) : null),
    [drawnGeometry],
  );
  const createFieldErrorMessage = createFieldMutation.isError ? errorToMessage(createFieldMutation.error) : "";

  useEffect(() => {
    if (!isAuthenticated) {
      setSelectedFarmId("");
      setImageryResults([]);
      setSelectedSceneId("");
      setLatestExportId("");
      latestExportStatusRef.current = "";
      return;
    }
    if (farms.length === 0) {
      setSelectedFarmId("");
      return;
    }

    const hasSelected = farms.some((farm) => farm.id === selectedFarmId);
    if (!hasSelected) {
      setSelectedFarmId(farms[0].id);
    }
  }, [isAuthenticated, farms, selectedFarmId]);

  useEffect(() => {
    setImageryResults([]);
    setSelectedSceneId("");
    setLatestAnalysisId("");
    latestAnalysisStatusRef.current = "";
    setLatestExportId("");
    latestExportStatusRef.current = "";
  }, [selectedFieldId]);

  useEffect(() => {
    if (!selectedFarmId) {
      setSelectedFieldId("");
      return;
    }
    if (fields.length === 0) {
      setSelectedFieldId("");
      return;
    }
    const hasSelectedField = fields.some((field) => field.id === selectedFieldId);
    if (!hasSelectedField) {
      setSelectedFieldId(fields[0].id);
    }
  }, [selectedFarmId, fields, selectedFieldId, setSelectedFieldId]);

  useEffect(() => {
    if (!alertsQuery.error) {
      return;
    }
    handleAuthFailure(alertsQuery.error, `Alerts failed: ${errorToMessage(alertsQuery.error)}`);
  }, [alertsQuery.error]);

  useEffect(() => {
    if (!farmsQuery.error) {
      return;
    }
    handleAuthFailure(farmsQuery.error, `Farm loading failed: ${errorToMessage(farmsQuery.error)}`);
  }, [farmsQuery.error]);

  useEffect(() => {
    if (!fieldsQuery.error) {
      return;
    }
    handleAuthFailure(fieldsQuery.error, `Field loading failed: ${errorToMessage(fieldsQuery.error)}`);
  }, [fieldsQuery.error]);

  useEffect(() => {
    if (!analysisStatusQuery.error) {
      return;
    }
    handleAuthFailure(analysisStatusQuery.error, `Analysis status check failed: ${errorToMessage(analysisStatusQuery.error)}`);
  }, [analysisStatusQuery.error]);

  useEffect(() => {
    if (!exportStatusQuery.error) {
      return;
    }
    handleAuthFailure(exportStatusQuery.error, `Export status check failed: ${errorToMessage(exportStatusQuery.error)}`);
  }, [exportStatusQuery.error]);

  useEffect(() => {
    const analysisJob = analysisStatusQuery.data;
    if (!analysisJob) {
      return;
    }

    const marker = `${analysisJob.id}:${analysisJob.status}`;
    if (latestAnalysisStatusRef.current === marker) {
      return;
    }
    latestAnalysisStatusRef.current = marker;

    if (analysisJob.status === "QUEUED") {
      setStatusMessage(`Analysis queued: ${analysisJob.id}`);
      return;
    }
    if (analysisJob.status === "RUNNING") {
      setStatusMessage(`Analysis running: ${analysisJob.id}`);
      return;
    }

    const result = asRecord(analysisJob.result_json);
    if (analysisJob.status === "SUCCEEDED") {
      setStatusMessage(formatAnalysisSuccessMessage(analysisJob.id, result));
      queryClient.invalidateQueries({ queryKey: ["timeseries", selectedFieldId, selectedIndex, token] });
      queryClient.invalidateQueries({ queryKey: ["alerts", token] });
      return;
    }

    if (analysisJob.status === "SKIPPED") {
      setStatusMessage(formatAnalysisSkippedMessage(analysisJob.id, result));
      queryClient.invalidateQueries({ queryKey: ["timeseries", selectedFieldId, selectedIndex, token] });
      queryClient.invalidateQueries({ queryKey: ["alerts", token] });
      return;
    }

    if (analysisJob.status === "FAILED") {
      setStatusMessage(`Analysis failed: ${analysisJob.error_message || analysisJob.id}`);
      queryClient.invalidateQueries({ queryKey: ["alerts", token] });
    }
  }, [analysisStatusQuery.data, queryClient, selectedFieldId, selectedIndex, token]);

  useEffect(() => {
    const exportJob = exportStatusQuery.data;
    if (!exportJob) {
      return;
    }

    const marker = `${exportJob.id}:${exportJob.status}`;
    if (latestExportStatusRef.current === marker) {
      return;
    }
    latestExportStatusRef.current = marker;

    if (exportJob.status === "RUNNING") {
      setStatusMessage(`Export running: ${exportJob.id}`);
      return;
    }
    if (exportJob.status === "SUCCEEDED") {
      setStatusMessage(`Export ready: ${exportJob.id}. Download is available in the Exports card.`);
      return;
    }
    if (exportJob.status === "FAILED") {
      setStatusMessage(`Export failed: ${exportJob.error_message || exportJob.id}`);
    }
  }, [exportStatusQuery.data]);

  const bootstrapFarmMutation = useMutation({
    mutationFn: async (payload: { organizationName: string; farmName: string }) => {
      const organization = await createOrganization({ name: payload.organizationName }, token);
      return createFarm({ organization_id: organization.id, name: payload.farmName }, token);
    },
    onSuccess: async (farm) => {
      await queryClient.invalidateQueries({ queryKey: ["farms", token] });
      setSelectedFarmId(farm.id);
      setStatusMessage(`Workspace created: ${farm.name}`);
    },
    onError: (error) => {
      handleAuthFailure(error, `Workspace creation failed: ${errorToMessage(error)}`);
    },
  });

  const createFarmMutation = useMutation({
    mutationFn: async (payload: { name: string }) => {
      const organizationId =
        farms.find((farm) => farm.id === selectedFarmId)?.organization_id ?? farms[0]?.organization_id;
      if (!organizationId) {
        throw new Error("No organization context available. Create your first workspace.");
      }
      return createFarm({ organization_id: organizationId, name: payload.name }, token);
    },
    onSuccess: async (farm) => {
      await queryClient.invalidateQueries({ queryKey: ["farms", token] });
      setSelectedFarmId(farm.id);
      setStatusMessage(`Farm created: ${farm.name}`);
    },
    onError: (error) => {
      handleAuthFailure(error, `Farm creation failed: ${errorToMessage(error)}`);
    },
  });

  return (
    <main className="relative h-screen overflow-hidden p-3 sm:p-4 lg:p-5">
      <div className="ui-grid-overlay" />
      <div className="relative z-10 flex h-full min-h-0 flex-col gap-3">
        <header className="ui-panel animate-panel shrink-0 flex flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div>
            <h1 className="text-lg font-bold tracking-tight text-[var(--ink-800)]">Field Monitor Hybrid</h1>
            <p className="text-xs text-[var(--ink-600)]">Polygon-first agricultural analytics with native and SR workflows.</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={isAuthenticated ? "success" : "warn"}>{isAuthenticated ? "Authenticated" : "Sign in required"}</Badge>
            <Badge variant={selectedFarmId ? "success" : "warn"}>{selectedFarmId ? "Farm selected" : "No farm"}</Badge>
            <Badge variant="soft">Index {selectedIndex}</Badge>
            <Badge variant="soft">Map {mapMode}</Badge>
            <Badge variant={selectedFieldId ? "success" : "warn"}>{selectedFieldId ? "Field selected" : "No field"}</Badge>
          </div>
        </header>

        <section className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[320px_minmax(0,1fr)_340px] xl:grid-cols-[340px_minmax(0,1fr)_360px]">
          <LeftPanel
            drawnAreaHa={drawnAreaHa}
            isAuthenticated={isAuthenticated}
            authEmail={authEmail}
            farms={farms}
            selectedFarmId={selectedFarmId}
            onFarmChange={setSelectedFarmId}
            onBootstrapFarm={async (payload) => {
              await bootstrapFarmMutation.mutateAsync(payload);
            }}
            onCreateFarm={async (payload) => {
              await createFarmMutation.mutateAsync(payload);
            }}
            onLogin={async (payload) => {
              await loginMutation.mutateAsync(payload);
            }}
            onRegister={async (payload) => {
              await registerMutation.mutateAsync(payload);
            }}
            onLogout={() => {
              clearSession();
              setSelectedFarmId("");
              setSelectedFieldId("");
              setLatestAnalysisId("");
              latestAnalysisStatusRef.current = "";
              setLatestExportId("");
              latestExportStatusRef.current = "";
              setStatusMessage("Signed out.");
            }}
            selectedIndex={selectedIndex}
            onIndexChange={setSelectedIndex}
            mapMode={mapMode}
            onMapModeChange={setMapMode}
            selectedSceneId={selectedSceneId}
            includeSrInAnalysis={includeSrInAnalysis}
            onIncludeSrChange={setIncludeSrInAnalysis}
            onCreateField={async ({ farmId, name }) => {
              await createFieldMutation.mutateAsync({ farmId, name });
            }}
            onUploadField={async ({ farmId, name, file }) => {
              await uploadMutation.mutateAsync({ farmId, name, file });
            }}
            onSearchImagery={async (payload) => {
              if (!selectedFieldId) throw new Error("Select or create a field first.");
              await imageryMutation.mutateAsync(payload);
            }}
            onRunAnalysis={async (payload) => {
              if (!selectedFieldId) throw new Error("Select or create a field first.");
              await analysisMutation.mutateAsync({
                ...payload,
                includeSr: payload.includeSr || mapMode !== "NATIVE",
                sceneId: selectedSceneId || undefined,
              });
            }}
            isCreatingField={createFieldMutation.isPending}
            isUploadingField={uploadMutation.isPending}
            isSearchingImagery={imageryMutation.isPending}
            isRunningAnalysis={analysisMutation.isPending}
            isBootstrappingFarm={bootstrapFarmMutation.isPending}
            isCreatingFarm={createFarmMutation.isPending}
            isLoggingIn={loginMutation.isPending}
            isRegistering={registerMutation.isPending}
            createFieldErrorMessage={createFieldErrorMessage}
          />

          <section className="ui-panel animate-panel relative h-full min-h-0 overflow-hidden p-2">
            <MapWorkspace
              mapMode={mapMode}
              onGeometryChange={setDrawnGeometry}
              imageryResults={imageryResults}
              selectedSceneId={selectedSceneId}
              onSceneSelect={setSelectedSceneId}
              selectedFieldId={selectedFieldId}
              selectedFieldGeometry={selectedFieldGeometry}
              points={points}
              selectedIndex={selectedIndex}
              token={token}
            />
            <div className="absolute bottom-4 right-4 z-10 max-w-[420px] rounded-xl border border-[var(--line-strong)] bg-[rgba(7,16,29,0.84)] px-4 py-2 text-xs font-medium text-[var(--ink-800)] shadow-[0_14px_26px_rgba(0,0,0,0.34)]">
              {statusMessage}
            </div>
          </section>

          <RightPanel
            isAuthenticated={isAuthenticated}
            fields={fields}
            selectedFieldId={selectedFieldId}
            onFieldChange={setSelectedFieldId}
            points={points}
            alerts={alerts}
            imageryResults={imageryResults}
            selectedSceneId={selectedSceneId}
            onSceneSelect={setSelectedSceneId}
            selectedIndex={selectedIndex}
            onAckAlert={async (alertId) => {
              await ackAlertMutation.mutateAsync(alertId);
            }}
            onClearTimeline={async () => {
              if (!selectedFieldId) throw new Error("Select a field first.");
              await clearTimelineMutation.mutateAsync();
            }}
            onClearAlerts={async () => {
              await clearAlertsMutation.mutateAsync();
            }}
            onCreateExport={async (format) => {
              if (!selectedFieldId) throw new Error("Select a field first.");
              await exportMutation.mutateAsync(format);
            }}
            onUpdateSchedule={async (payload) => {
              if (!selectedFieldId) throw new Error("Select a field first.");
              await scheduleMutation.mutateAsync(payload);
            }}
            latestAnalysis={analysisStatusQuery.data ?? null}
            isAnalysisPolling={analysisStatusQuery.isFetching}
            latestExport={exportStatusQuery.data ?? null}
            isExporting={exportMutation.isPending}
            isExportPolling={exportStatusQuery.isFetching}
            isAcknowledgingAlert={ackAlertMutation.isPending}
            isClearingTimeline={clearTimelineMutation.isPending}
            isClearingAlerts={clearAlertsMutation.isPending}
            isUpdatingSchedule={scheduleMutation.isPending}
          />
        </section>
      </div>
    </main>
  );
}
