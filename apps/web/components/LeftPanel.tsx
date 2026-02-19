"use client";

import { ChangeEvent, useMemo, useState } from "react";
import { DateRange } from "react-day-picker";

import { IndexName, MapMode } from "@fieldmonitor/shared-types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHint, CardTitle } from "@/components/ui/card";
import { DateRangePicker } from "@/components/ui/date-range-picker";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { FarmItem } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LeftPanelProps {
  drawnAreaHa: number | null;
  isAuthenticated: boolean;
  authEmail: string;
  farms: FarmItem[];
  selectedFarmId: string;
  onFarmChange: (farmId: string) => void;
  onBootstrapFarm: (payload: { organizationName: string; farmName: string }) => Promise<void>;
  onCreateFarm: (payload: { name: string }) => Promise<void>;
  onLogin: (payload: { email: string; password: string }) => Promise<void>;
  onRegister: (payload: { email: string; password: string; fullName?: string }) => Promise<void>;
  onLogout: () => void;
  selectedIndex: IndexName;
  onIndexChange: (index: IndexName) => void;
  mapMode: MapMode;
  onMapModeChange: (mode: MapMode) => void;
  selectedSceneId?: string;
  includeSrInAnalysis: boolean;
  onIncludeSrChange: (value: boolean) => void;
  onCreateField: (payload: { farmId: string; name: string }) => Promise<void>;
  onUploadField: (payload: { farmId: string; name: string; file: File }) => Promise<void>;
  onSearchImagery: (payload: { dateFrom?: string; dateTo?: string; maxCloud?: number }) => Promise<void>;
  onRunAnalysis: (payload: { dateFrom?: string; dateTo?: string; maxCloud?: number; includeSr: boolean }) => Promise<void>;
  isCreatingField: boolean;
  isUploadingField: boolean;
  isSearchingImagery: boolean;
  isRunningAnalysis: boolean;
  isBootstrappingFarm: boolean;
  isCreatingFarm: boolean;
  isLoggingIn: boolean;
  isRegistering: boolean;
  createFieldErrorMessage?: string;
}

const INDICES: IndexName[] = ["NDVI", "NDMI", "NDWI", "EVI", "NDRE", "SAVI"];
const MAP_MODES: Array<{ key: MapMode; label: string; description: string }> = [
  { key: "NATIVE", label: "Native", description: "Original Sentinel view. Best default for trusted analysis." },
  { key: "SR", label: "SR", description: "Model-enhanced close-up view (MODEL_DERIVED), useful for visual detail." },
  { key: "SIDE_BY_SIDE", label: "Split", description: "Native and SR shown side-by-side for direct comparison." },
  { key: "SWIPE", label: "Swipe", description: "Single map with a draggable comparison between Native and SR." },
];

export function LeftPanel({
  drawnAreaHa = null,
  isAuthenticated,
  authEmail,
  farms = [],
  selectedFarmId = "",
  onFarmChange,
  onBootstrapFarm,
  onCreateFarm,
  onLogin,
  onRegister,
  onLogout,
  selectedIndex,
  onIndexChange,
  mapMode,
  onMapModeChange,
  selectedSceneId = "",
  includeSrInAnalysis,
  onIncludeSrChange,
  onCreateField,
  onUploadField,
  onSearchImagery,
  onRunAnalysis,
  isCreatingField,
  isUploadingField,
  isSearchingImagery,
  isRunningAnalysis,
  isBootstrappingFarm,
  isCreatingFarm,
  isLoggingIn,
  isRegistering,
  createFieldErrorMessage,
}: LeftPanelProps) {
  const safeFarms = Array.isArray(farms) ? farms : [];
  const [authMode, setAuthMode] = useState<"LOGIN" | "REGISTER">("LOGIN");
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [registerName, setRegisterName] = useState("");

  const [organizationName, setOrganizationName] = useState("My Organization");
  const [firstFarmName, setFirstFarmName] = useState("Main Farm");
  const [newFarmName, setNewFarmName] = useState("");

  const [fieldName, setFieldName] = useState("Field 1");
  const [file, setFile] = useState<File | null>(null);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(undefined);
  const [maxCloud, setMaxCloud] = useState(20);

  const authBusy = isLoggingIn || isRegistering;
  const hasFarms = safeFarms.length > 0;
  const canRunFieldActions = isAuthenticated && hasFarms && Boolean(selectedFarmId);
  const hasDrawnArea = typeof drawnAreaHa === "number" && Number.isFinite(drawnAreaHa);
  const exceedsAreaCap = hasDrawnArea && drawnAreaHa > 10_000;
  const normalizedFieldName = fieldName.trim();
  const selectedFarm = useMemo(() => safeFarms.find((farm) => farm.id === selectedFarmId), [safeFarms, selectedFarmId]);

  const handleUploadChange = (event: ChangeEvent<HTMLInputElement>) => {
    const picked = event.target.files?.[0] ?? null;
    setFile(picked);
  };

  const toIsoDate = (value?: Date): string | undefined => {
    if (!value) {
      return undefined;
    }
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };
  const dateFrom = toIsoDate(dateRange?.from);
  const dateTo = toIsoDate(dateRange?.to);

  const invoke = async (task: () => Promise<void>) => {
    try {
      await task();
    } catch {
      // status messages are handled by parent mutations
    }
  };

  const submitAuth = async () => {
    const email = loginEmail.trim().toLowerCase();
    if (!email || !loginPassword) {
      return;
    }

    if (authMode === "LOGIN") {
      await onLogin({ email, password: loginPassword });
      return;
    }

    await onRegister({
      email,
      password: loginPassword,
      fullName: registerName.trim() ? registerName.trim() : undefined,
    });
  };

  return (
    <aside className="panel-scroll ui-panel animate-panel flex h-full w-full flex-col gap-4 overflow-y-auto p-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold tracking-tight text-[var(--ink-800)]">Operations</h2>
          <p className="text-xs text-[var(--ink-600)]">Field setup, filtering, and analysis orchestration.</p>
        </div>
        <Badge variant={isAuthenticated ? "success" : "warn"}>{isAuthenticated ? "Signed in" : "Signed out"}</Badge>
      </div>

      <Card>
        <CardTitle>Account</CardTitle>
        {!isAuthenticated ? (
          <>
            <CardHint className="mb-3 mt-1">Use this form to authenticate. No terminal token copy is required.</CardHint>

            <div className="mb-3 grid grid-cols-2 gap-2">
              <button
                type="button"
                className={cn(
                  "rounded-md border px-2 py-1.5 text-xs font-semibold transition",
                  authMode === "LOGIN"
                    ? "border-[var(--accent-500)] bg-[var(--accent-500)] text-[#04141a]"
                    : "border-[var(--line)] bg-[var(--surface-1)] text-[var(--ink-700)] hover:bg-[var(--surface-2)]",
                )}
                onClick={() => setAuthMode("LOGIN")}
                disabled={authBusy}
              >
                Login
              </button>
              <button
                type="button"
                className={cn(
                  "rounded-md border px-2 py-1.5 text-xs font-semibold transition",
                  authMode === "REGISTER"
                    ? "border-[var(--accent-500)] bg-[var(--accent-500)] text-[#04141a]"
                    : "border-[var(--line)] bg-[var(--surface-1)] text-[var(--ink-700)] hover:bg-[var(--surface-2)]",
                )}
                onClick={() => setAuthMode("REGISTER")}
                disabled={authBusy}
              >
                Register
              </button>
            </div>

            <div className="space-y-2">
              {authMode === "REGISTER" && (
                <Input
                  placeholder="Full name (optional)"
                  value={registerName}
                  onChange={(event) => setRegisterName(event.target.value)}
                  disabled={authBusy}
                />
              )}
              <Input
                placeholder="Email"
                type="email"
                value={loginEmail}
                onChange={(event) => setLoginEmail(event.target.value)}
                disabled={authBusy}
              />
              <Input
                placeholder="Password"
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
                disabled={authBusy}
              />
              <Button
                className="w-full"
                disabled={!loginEmail.trim() || !loginPassword || authBusy}
                onClick={() => void invoke(submitAuth)}
              >
                {authMode === "LOGIN"
                  ? isLoggingIn
                    ? "Signing in..."
                    : "Sign In"
                  : isRegistering
                    ? "Creating account..."
                    : "Create Account"}
              </Button>
            </div>
          </>
        ) : (
          <>
            <CardHint className="mb-3 mt-1">Authenticated as {authEmail || "current user"}.</CardHint>
            <Button variant="outline" className="w-full" onClick={onLogout}>
              Sign Out
            </Button>
          </>
        )}
      </Card>

      <Card>
        <CardTitle>Farm Context</CardTitle>
        {!isAuthenticated ? (
          <CardHint className="mt-1">Sign in to load or create your farm workspace.</CardHint>
        ) : hasFarms ? (
          <>
            <CardHint className="mb-3 mt-1">Select a farm for new field operations.</CardHint>
            <select
              className="h-10 w-full rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 text-sm text-[var(--ink-800)] outline-none transition focus:border-[var(--accent-400)] focus:ring-2 focus:ring-[var(--accent-200)]"
              value={selectedFarmId}
              onChange={(event) => onFarmChange(event.target.value)}
            >
              {safeFarms.map((farm) => (
                <option key={farm.id} value={farm.id}>
                  {farm.name}
                </option>
              ))}
            </select>
            <div className="mt-3 space-y-2">
              <Input
                placeholder="New farm name"
                value={newFarmName}
                onChange={(event) => setNewFarmName(event.target.value)}
                disabled={isCreatingFarm}
              />
              <Button
                variant="secondary"
                className="w-full"
                disabled={!newFarmName.trim() || isCreatingFarm}
                onClick={() =>
                  void invoke(async () => {
                    await onCreateFarm({ name: newFarmName.trim() });
                    setNewFarmName("");
                  })
                }
              >
                {isCreatingFarm ? "Creating farm..." : "Create Farm"}
              </Button>
            </div>
            {selectedFarm && (
              <CardHint className="mt-3">Active farm: {selectedFarm.name}</CardHint>
            )}
          </>
        ) : (
          <>
            <CardHint className="mb-3 mt-1">No farms found. Create your first organization and farm once.</CardHint>
            <div className="space-y-2">
              <Input
                placeholder="Organization name"
                value={organizationName}
                onChange={(event) => setOrganizationName(event.target.value)}
                disabled={isBootstrappingFarm}
              />
              <Input
                placeholder="First farm name"
                value={firstFarmName}
                onChange={(event) => setFirstFarmName(event.target.value)}
                disabled={isBootstrappingFarm}
              />
              <Button
                className="w-full"
                disabled={!organizationName.trim() || !firstFarmName.trim() || isBootstrappingFarm}
                onClick={() =>
                  void invoke(() =>
                    onBootstrapFarm({
                      organizationName: organizationName.trim(),
                      farmName: firstFarmName.trim(),
                    }),
                  )
                }
              >
                {isBootstrappingFarm ? "Creating workspace..." : "Create Organization + Farm"}
              </Button>
            </div>
          </>
        )}
      </Card>

      <Card>
        <CardTitle>AOI Setup</CardTitle>
        <CardHint className="mb-3 mt-1">Draw a polygon on the map, then save or upload field geometry.</CardHint>
        {hasDrawnArea && (
          <CardHint
            className={cn(
              "mb-3 rounded-md border px-2 py-1",
              exceedsAreaCap
                ? "border-[var(--warn-200)] bg-[var(--warn-100)] text-[var(--warn-700)]"
                : "border-[var(--line)] bg-[var(--surface-1)]",
            )}
          >
            Drawn area: {hasDrawnArea ? drawnAreaHa.toFixed(2) : "0.00"} ha {exceedsAreaCap ? "(limit is 10,000 ha)" : ""}
          </CardHint>
        )}

        <div className="space-y-2">
          <Input
            placeholder="Field name"
            value={fieldName}
            onChange={(event) => setFieldName(event.target.value)}
            disabled={!canRunFieldActions}
          />

          <Button
            className="w-full"
            disabled={!canRunFieldActions || !normalizedFieldName || isCreatingField || exceedsAreaCap}
            onClick={() =>
              selectedFarmId &&
              void invoke(() => onCreateField({ farmId: selectedFarmId, name: normalizedFieldName }))
            }
          >
            {isCreatingField ? "Saving polygon..." : "Save Drawn Polygon"}
          </Button>
          {createFieldErrorMessage && (
            <CardHint className="rounded-md border border-[var(--danger-200)] bg-[var(--danger-100)] px-2 py-1 text-[var(--danger-700)]">
              {createFieldErrorMessage}
            </CardHint>
          )}

          <label
            className={cn(
              "group flex w-full items-center justify-between rounded-lg border border-dashed border-[var(--line-strong)] px-3 py-2 text-xs text-[var(--ink-600)] transition",
              canRunFieldActions ? "cursor-pointer hover:bg-[var(--surface-2)]" : "cursor-not-allowed opacity-60",
            )}
          >
            <span>{file ? file.name : "Choose GeoJSON / KML / ZIP Shapefile"}</span>
            <span className="rounded bg-[var(--surface-1)] px-2 py-1 font-semibold">Browse</span>
            <input
              className="hidden"
              type="file"
              accept=".geojson,.json,.kml,.zip"
              onChange={handleUploadChange}
              disabled={!canRunFieldActions}
            />
          </label>

          <Button
            variant="secondary"
            className="w-full"
            disabled={!canRunFieldActions || !file || !normalizedFieldName || isUploadingField || exceedsAreaCap}
            onClick={() =>
              file &&
              selectedFarmId &&
              void invoke(() => onUploadField({ farmId: selectedFarmId, name: normalizedFieldName, file }))
            }
          >
            {isUploadingField ? "Uploading..." : "Upload Polygon File"}
          </Button>
        </div>
      </Card>

      <Card>
        <CardTitle>Visual Controls</CardTitle>
        <CardHint className="mb-3 mt-1">Switch active index and comparison mode instantly.</CardHint>

        <div className="mb-3 grid grid-cols-3 gap-2">
          {INDICES.map((index) => (
            <button
              key={index}
              type="button"
              onClick={() => onIndexChange(index)}
              className={cn(
                "rounded-md border px-2 py-1.5 text-xs font-semibold transition",
                selectedIndex === index
                  ? "border-[var(--accent-500)] bg-[var(--accent-500)] text-[#04141a]"
                  : "border-[var(--line)] bg-[var(--surface-1)] text-[var(--ink-700)] hover:bg-[var(--surface-2)]",
              )}
            >
              {index}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-2">
          {MAP_MODES.map((mode) => (
            <button
              key={mode.key}
              type="button"
              onClick={() => onMapModeChange(mode.key)}
              title={mode.description}
              className={cn(
                "rounded-md border px-2 py-1.5 text-xs font-semibold transition",
                mapMode === mode.key
                  ? "border-[var(--accent-500)] bg-[var(--accent-100)] text-[var(--accent-700)]"
                  : "border-[var(--line)] bg-[var(--surface-1)] text-[var(--ink-700)] hover:bg-[var(--surface-2)]",
              )}
            >
              {mode.label}
            </button>
          ))}
        </div>
        <CardHint className="mt-3">
          {MAP_MODES.find((mode) => mode.key === mapMode)?.description}
        </CardHint>
      </Card>

      <Card>
        <CardTitle>Acquisition Filters</CardTitle>
        <CardHint className="mb-3 mt-1">Control date range and cloud threshold for scene search.</CardHint>
        <DateRangePicker value={dateRange} onChange={setDateRange} disabled={!isAuthenticated} />

        <div className="mt-3 rounded-lg border border-[var(--line)] bg-[var(--surface-1)] px-3 py-2">
          <div className="mb-2 flex items-center justify-between text-xs font-semibold text-[var(--ink-600)]">
            <span>Max cloud cover</span>
            <Badge variant="soft">{maxCloud}%</Badge>
          </div>
          <input
            className="w-full accent-[var(--accent-600)]"
            type="range"
            min={0}
            max={100}
            value={maxCloud}
            onChange={(event) => setMaxCloud(Number(event.target.value))}
            disabled={!isAuthenticated}
          />
        </div>

        <Button
          variant="outline"
          className="mt-3 w-full"
          disabled={!isAuthenticated || isSearchingImagery}
          onClick={() => void invoke(() => onSearchImagery({ dateFrom, dateTo, maxCloud }))}
        >
          {isSearchingImagery ? "Searching scenes..." : "Search Imagery"}
        </Button>
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <CardTitle>Run Analysis</CardTitle>
          <Switch checked={includeSrInAnalysis} onCheckedChange={onIncludeSrChange} disabled={!isAuthenticated || isRunningAnalysis} />
        </div>
        <CardHint className="mb-3">
          {isAuthenticated
            ? "Enable SR to generate close-up model-derived imagery. SR indices still depend on org feature flag."
            : "Sign in first to run analysis and unlock exports and alerts."}
        </CardHint>
        {selectedSceneId && (
          <CardHint className="mb-3 rounded-md border border-[var(--line)] bg-[var(--surface-1)] px-2 py-1">
            Selected scene will be used: <span className="font-semibold text-[var(--ink-700)]">{selectedSceneId}</span>
          </CardHint>
        )}

        <Button
          className="w-full"
          disabled={!isAuthenticated || isRunningAnalysis}
          onClick={() =>
            void invoke(() => onRunAnalysis({ dateFrom, dateTo, maxCloud, includeSr: includeSrInAnalysis }))
          }
        >
          {isRunningAnalysis ? "Queueing analysis..." : "Run Analysis"}
        </Button>
      </Card>
    </aside>
  );
}
