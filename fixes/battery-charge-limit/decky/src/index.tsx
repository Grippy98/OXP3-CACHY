import { callable, definePlugin } from "@decky/api";
import { DropdownItem, PanelSection, PanelSectionRow } from "@decky/ui";
import { useCallback, useEffect, useRef, useState } from "react";

type Mode = "auto" | "inhibit-charge-awake" | "inhibit-charge";
type Status = {
  ok: boolean;
  mode?: Mode | null;
  supported_modes?: Mode[];
  limit?: number | null;
  percentage?: number | null;
  error?: string | null;
};
const getStatus = callable<[], Status>("get_status");
const setMode = callable<[mode: Mode], Status>("set_mode");
const OPTIONS: { data: Mode; label: string }[] = [
  { data: "auto", label: "Automatic charging" },
  { data: "inhibit-charge-awake", label: "Bypass while awake" },
  { data: "inhibit-charge", label: "Bypass always" },
];

function ChargePanel() {
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const mounted = useRef(false);
  const generation = useRef(0);
  const inFlight = useRef(false);
  const request = useCallback(async (operation: () => Promise<Status>) => {
    if (!mounted.current || inFlight.current) return;
    const current = generation.current;
    inFlight.current = true;
    setBusy(true);
    try {
      const result = await operation();
      if (mounted.current && generation.current === current) setStatus(result);
    } catch (error) {
      if (mounted.current && generation.current === current) {
        setStatus({ ok: false, error: error instanceof Error ? error.message : "Charge controls are unavailable." });
      }
    } finally {
      inFlight.current = false;
      if (mounted.current && generation.current === current) setBusy(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    generation.current += 1;
    void request(getStatus);
    const timer = setInterval(() => void request(getStatus), 5000);
    return () => {
      mounted.current = false;
      generation.current += 1;
      clearInterval(timer);
    };
  }, [request]);

  const options = OPTIONS.filter((option) => status?.supported_modes?.includes(option.data));
  return (
    <PanelSection title="Charging">
      <PanelSectionRow>
        <div>
          <div>Battery: {status?.percentage == null ? "—" : `${status.percentage}%`}</div>
          <div>Charge ceiling: {status?.limit == null ? "—" : `${status.limit}%`}</div>
        </div>
      </PanelSectionRow>
      {status?.ok && options.length > 0 ? (
        <PanelSectionRow>
          <DropdownItem
            label="Charge mode"
            rgOptions={options}
            selectedOption={status.mode ?? undefined}
            disabled={busy}
            onChange={(option) => void request(() => setMode(option.data as Mode))}
          />
        </PanelSectionRow>
      ) : null}
      <PanelSectionRow>
        <div style={{ fontSize: "0.85em", opacity: 0.8 }}>
          Charge mode is independent of the ceiling in Steam Settings → Power.
          {status?.mode === "inhibit-charge-awake" ? " Charging can resume during sleep or shutdown." : ""}
        </div>
      </PanelSectionRow>
      {status?.error ? <PanelSectionRow><div role="alert">{status.error}</div></PanelSectionRow> : null}
      {status === null ? <PanelSectionRow><div>Reading charge controls…</div></PanelSectionRow> : null}
    </PanelSection>
  );
}

const BatteryIcon = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="2" y="6" width="18" height="12" rx="2" />
    <path d="M22 10v4M7 12h8M11 8v8" />
  </svg>
);

export default definePlugin(() => ({
  name: "OXP3 Charge Controls",
  titleView: <div>OXP3 Charge Controls</div>,
  content: <ChargePanel />,
  icon: <BatteryIcon />,
}));
