"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Loader2, Plus, Trash2, ChevronDown, Sparkles, Check, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  createCompetitor,
  updateCompetitor,
  discoverCompetitorConfig,
  type CompetitorFormData,
} from "@/app/(dashboard)/admin/actions";

interface Entity {
  label: string;
  trustpilot_slug: string | null;
  fpa_slug: string | null;
  ios_app_id: string | null;
  android_package: string | null;
}

interface ScraperConfig {
  pricing_url: string | null;
  pricing_wait_selector: string | null;
  account_urls: string[];
  promo_url: string | null;
  youtube_query: string | null;
  facebook_slug: string | null;
  instagram_handle: string | null;
  x_handle: string | null;
  wikifx_id: string | null;
  tradingfinder_slug: string | null;
  dailyforex_slug: string | null;
  myfxbook_slug: string | null;
  entities: Entity[];
  known_leverage: string[] | null;
  known_account_types: string[] | null;
  known_min_deposit_usd: number | null;
}

const EMPTY_ENTITY: Entity = {
  label: "",
  trustpilot_slug: null,
  fpa_slug: null,
  ios_app_id: null,
  android_package: null,
};

const EMPTY_CONFIG: ScraperConfig = {
  pricing_url: null,
  pricing_wait_selector: null,
  account_urls: [],
  promo_url: null,
  youtube_query: null,
  facebook_slug: null,
  instagram_handle: null,
  x_handle: null,
  wikifx_id: null,
  tradingfinder_slug: null,
  dailyforex_slug: null,
  myfxbook_slug: null,
  entities: [{ ...EMPTY_ENTITY }],
  known_leverage: null,
  known_account_types: null,
  known_min_deposit_usd: null,
};

interface Props {
  open: boolean;
  onClose: () => void;
  editData?: {
    id: string;
    name: string;
    tier: number;
    website: string;
    isSelf: number;
    scraperConfig: ScraperConfig | null;
  } | null;
}

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function Section({
  title,
  badge,
  defaultOpen = true,
  children,
}: {
  title: string;
  badge?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-50 text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors"
      >
        <span className="flex items-center gap-2">
          {title}
          {badge != null && badge > 0 && (
            <span className="px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-emerald-50 text-emerald-600 border border-emerald-200">
              {badge} found
            </span>
          )}
        </span>
        <ChevronDown
          className={cn("w-4 h-4 text-gray-400 transition-transform", open && "rotate-180")}
        />
      </button>
      {open && <div className="p-4 space-y-3">{children}</div>}
    </div>
  );
}

function Input({
  label,
  value,
  onChange,
  placeholder,
  disabled,
  discovered,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
  discovered?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider flex items-center gap-1">
        {label}
        {discovered && <Check className="w-3 h-3 text-emerald-500" />}
      </span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className={cn(
          "mt-1 block w-full rounded-lg border px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-primary focus:ring-1 focus:ring-primary disabled:bg-gray-50 disabled:text-gray-400",
          discovered ? "border-emerald-200 bg-emerald-50/30" : "border-gray-200"
        )}
      />
    </label>
  );
}

// Inner form — remounted via key when editData changes
function CompetitorFormInner({ onClose, editData }: Omit<Props, "open">) {
  const router = useRouter();
  const isEdit = !!editData;

  const [step, setStep] = useState<"input" | "review">(isEdit ? "review" : "input");
  const [name, setName] = useState(editData?.name ?? "");
  const [id, setId] = useState(editData?.id ?? "");
  const [tier, setTier] = useState(editData?.tier ?? 2);
  const [website, setWebsite] = useState(editData?.website ?? "");
  const [config, setConfig] = useState<ScraperConfig>(
    editData?.scraperConfig ?? { ...EMPTY_CONFIG, entities: [{ ...EMPTY_ENTITY }] }
  );
  const [saving, setSaving] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [discoveryWarnings, setDiscoveryWarnings] = useState<string[]>([]);
  const [discovered, setDiscovered] = useState<Set<string>>(new Set());

  function handleNameChange(v: string) {
    setName(v);
    if (!isEdit) setId(slugify(v));
  }

  function updateConfig<K extends keyof ScraperConfig>(key: K, value: ScraperConfig[K]) {
    setConfig((prev) => ({ ...prev, [key]: value }));
  }

  function updateEntity(idx: number, field: keyof Entity, value: string) {
    setConfig((prev) => {
      const entities = [...prev.entities];
      entities[idx] = { ...entities[idx], [field]: value || null };
      return { ...prev, entities };
    });
  }

  function addEntity() {
    setConfig((prev) => ({
      ...prev,
      entities: [...prev.entities, { ...EMPTY_ENTITY }],
    }));
  }

  function removeEntity(idx: number) {
    setConfig((prev) => ({
      ...prev,
      entities: prev.entities.filter((_, i) => i !== idx),
    }));
  }

  function updateAccountUrl(idx: number, value: string) {
    setConfig((prev) => {
      const urls = [...prev.account_urls];
      urls[idx] = value;
      return { ...prev, account_urls: urls };
    });
  }

  function addAccountUrl() {
    setConfig((prev) => ({
      ...prev,
      account_urls: [...prev.account_urls, ""],
    }));
  }

  function removeAccountUrl(idx: number) {
    setConfig((prev) => ({
      ...prev,
      account_urls: prev.account_urls.filter((_, i) => i !== idx),
    }));
  }

  // Auto-discover config from website
  async function handleDiscover() {
    if (!name.trim() || !website.trim()) {
      setError("Enter a name and website first");
      return;
    }
    setError(null);
    setDiscovering(true);
    setDiscoveryWarnings([]);

    const domain = website.replace(/^https?:\/\//, "").replace(/\/$/, "");
    const { config: found, errors } = await discoverCompetitorConfig(name, domain);

    // Build new config, merging discovered values
    const newConfig = { ...EMPTY_CONFIG };
    const foundKeys = new Set<string>();

    if (found.pricing_url) { newConfig.pricing_url = found.pricing_url; foundKeys.add("pricing_url"); }
    if (found.account_urls?.length) { newConfig.account_urls = found.account_urls; foundKeys.add("account_urls"); }
    if (found.promo_url) { newConfig.promo_url = found.promo_url; foundKeys.add("promo_url"); }
    if (found.youtube_query) { newConfig.youtube_query = found.youtube_query; foundKeys.add("youtube_query"); }
    if (found.facebook_slug) { newConfig.facebook_slug = found.facebook_slug; foundKeys.add("facebook_slug"); }
    if (found.instagram_handle) { newConfig.instagram_handle = found.instagram_handle; foundKeys.add("instagram_handle"); }
    if (found.x_handle) { newConfig.x_handle = found.x_handle; foundKeys.add("x_handle"); }
    if (found.wikifx_id) { newConfig.wikifx_id = found.wikifx_id; foundKeys.add("wikifx_id"); }
    if (found.tradingfinder_slug) { newConfig.tradingfinder_slug = found.tradingfinder_slug; foundKeys.add("tradingfinder_slug"); }
    if (found.dailyforex_slug) { newConfig.dailyforex_slug = found.dailyforex_slug; foundKeys.add("dailyforex_slug"); }
    if (found.myfxbook_slug) { newConfig.myfxbook_slug = found.myfxbook_slug; foundKeys.add("myfxbook_slug"); }

    // Build entity from discovered data
    const entity: Entity = {
      label: name,
      trustpilot_slug: found.trustpilot_slug ?? domain,
      fpa_slug: slugify(name),
      ios_app_id: found.ios_app_id ?? null,
      android_package: found.android_package ?? null,
    };
    newConfig.entities = [entity];
    if (found.trustpilot_slug) foundKeys.add("trustpilot_slug");
    if (found.ios_app_id) foundKeys.add("ios_app_id");
    if (found.android_package) foundKeys.add("android_package");

    setConfig(newConfig);
    setDiscovered(foundKeys);
    setDiscoveryWarnings(errors);
    setDiscovering(false);
    setStep("review");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);

    const formData: CompetitorFormData = {
      id,
      name,
      tier,
      website,
      isSelf: !!editData?.isSelf,
      scraperConfig: config,
    };

    const result = isEdit
      ? await updateCompetitor(editData!.id, formData)
      : await createCompetitor(formData);

    setSaving(false);

    if ("error" in result && result.error) {
      setError(result.error);
      return;
    }

    router.refresh();
    onClose();
  }

  // Count discovered items per section
  const socialCount = ["facebook_slug", "instagram_handle", "x_handle", "youtube_query"].filter((k) => discovered.has(k)).length;
  const slugCount = ["wikifx_id", "tradingfinder_slug", "dailyforex_slug", "myfxbook_slug"].filter((k) => discovered.has(k)).length;
  const entityCount = ["trustpilot_slug", "ios_app_id", "android_package"].filter((k) => discovered.has(k)).length;

  return (
    <>
      <DialogHeader>
        <DialogTitle>
          {isEdit ? `Edit ${editData.name}` : step === "input" ? "Add Competitor" : "Review & Save"}
        </DialogTitle>
      </DialogHeader>

      {/* Step 1: Name + Website + Auto-detect */}
      {step === "input" && !isEdit && (
          <div className="space-y-4 mt-2">
            {error && (
              <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
                {error}
              </div>
            )}
            <p className="text-sm text-gray-500">
              Enter the broker name and website. We&apos;ll auto-detect URLs, social handles, and platform IDs.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Name" value={name} onChange={handleNameChange} placeholder="e.g. OctaFX" />
              <Input label="Website" value={website} onChange={setWebsite} placeholder="e.g. octafx.com" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input label="ID (slug)" value={id} onChange={setId} placeholder="auto-generated" />
              <label className="block">
                <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider">Tier</span>
                <select
                  value={tier}
                  onChange={(e) => setTier(Number(e.target.value))}
                  className="mt-1 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 focus:border-primary focus:ring-1 focus:ring-primary"
                >
                  <option value={1}>Tier 1 — Major</option>
                  <option value={2}>Tier 2 — Secondary</option>
                </select>
              </label>
            </div>
            <div className="flex items-center justify-between pt-2">
              <button
                type="button"
                onClick={() => {
                  // Skip auto-detect, go straight to manual form
                  setConfig({ ...EMPTY_CONFIG, entities: [{ ...EMPTY_ENTITY, label: name }] });
                  setStep("review");
                }}
                className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
              >
                Skip, fill manually
              </button>
              <button
                type="button"
                onClick={handleDiscover}
                disabled={discovering || !name.trim() || !website.trim()}
                className={cn(
                  "px-5 py-2.5 text-sm font-medium rounded-lg border transition-colors flex items-center gap-2 disabled:cursor-not-allowed",
                  discovering
                    ? "bg-gray-100 text-gray-400 border-gray-200"
                    : "bg-primary text-white border-primary hover:bg-primary/90 active:bg-primary/80"
                )}
              >
                {discovering ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Scanning website...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Auto-detect config
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Review pre-filled form */}
        {step === "review" && (
          <form onSubmit={handleSubmit} className="space-y-4 mt-2">
            {error && (
              <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
                {error}
              </div>
            )}

            {/* Discovery summary */}
            {!isEdit && discovered.size > 0 && (
              <div className="px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm flex items-start gap-2">
                <Check className="w-4 h-4 shrink-0 mt-0.5" />
                <span>
                  Auto-detected {discovered.size} field{discovered.size !== 1 ? "s" : ""}.
                  Fields marked with <Check className="w-3 h-3 inline text-emerald-500" /> were found automatically.
                  Review and adjust before saving.
                </span>
              </div>
            )}
            {discoveryWarnings.length > 0 && (
              <div className="px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-sm flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{discoveryWarnings.join(". ")}</span>
              </div>
            )}

            {/* Basic Info */}
            <Section title="Basic Info">
              <div className="grid grid-cols-2 gap-3">
                <Input label="Name" value={name} onChange={handleNameChange} placeholder="e.g. IC Markets" />
                <Input label="ID (slug)" value={id} onChange={setId} placeholder="e.g. ic-markets" disabled={isEdit} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider">Tier</span>
                  <select
                    value={tier}
                    onChange={(e) => setTier(Number(e.target.value))}
                    className="mt-1 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-900 focus:border-primary focus:ring-1 focus:ring-primary"
                  >
                    <option value={1}>Tier 1 — Major competitor</option>
                    <option value={2}>Tier 2 — Secondary competitor</option>
                  </select>
                </label>
                <Input label="Website" value={website} onChange={setWebsite} placeholder="e.g. icmarkets.com" />
              </div>
            </Section>

            {/* Scraper URLs */}
            <Section
              title="Scraper URLs"
              badge={["pricing_url", "promo_url", "account_urls"].filter((k) => discovered.has(k)).length}
            >
              <Input
                label="Pricing URL"
                value={config.pricing_url ?? ""}
                onChange={(v) => updateConfig("pricing_url", v || null)}
                placeholder="https://..."
                discovered={discovered.has("pricing_url")}
              />
              <Input
                label="Promo URL"
                value={config.promo_url ?? ""}
                onChange={(v) => updateConfig("promo_url", v || null)}
                placeholder="https://..."
                discovered={discovered.has("promo_url")}
              />
              <Input
                label="Wait Selector (optional)"
                value={config.pricing_wait_selector ?? ""}
                onChange={(v) => updateConfig("pricing_wait_selector", v || null)}
                placeholder="CSS selector to wait for"
              />
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] text-gray-500 font-medium uppercase tracking-wider flex items-center gap-1">
                    Account URLs
                    {discovered.has("account_urls") && <Check className="w-3 h-3 text-emerald-500" />}
                  </span>
                  <button
                    type="button"
                    onClick={addAccountUrl}
                    className="text-xs text-primary hover:text-primary/80 flex items-center gap-0.5"
                  >
                    <Plus className="w-3 h-3" /> Add
                  </button>
                </div>
                <div className="space-y-2">
                  {config.account_urls.map((url, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <input
                        type="text"
                        value={url}
                        onChange={(e) => updateAccountUrl(i, e.target.value)}
                        placeholder="https://..."
                        className={cn(
                          "flex-1 rounded-lg border px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-primary focus:ring-1 focus:ring-primary",
                          discovered.has("account_urls") ? "border-emerald-200 bg-emerald-50/30" : "border-gray-200"
                        )}
                      />
                      <button
                        type="button"
                        onClick={() => removeAccountUrl(i)}
                        className="text-gray-400 hover:text-red-500 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                  {config.account_urls.length === 0 && (
                    <p className="text-xs text-gray-400">No account URLs configured</p>
                  )}
                </div>
              </div>
            </Section>

            {/* Social Handles */}
            <Section title="Social Handles" badge={socialCount} defaultOpen={socialCount > 0}>
              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="YouTube Query"
                  value={config.youtube_query ?? ""}
                  onChange={(v) => updateConfig("youtube_query", v || null)}
                  placeholder="e.g. IC Markets trading"
                  discovered={discovered.has("youtube_query")}
                />
                <Input
                  label="Facebook Slug"
                  value={config.facebook_slug ?? ""}
                  onChange={(v) => updateConfig("facebook_slug", v || null)}
                  placeholder="e.g. icmarkets"
                  discovered={discovered.has("facebook_slug")}
                />
                <Input
                  label="Instagram Handle"
                  value={config.instagram_handle ?? ""}
                  onChange={(v) => updateConfig("instagram_handle", v || null)}
                  placeholder="e.g. icmarketsglobal"
                  discovered={discovered.has("instagram_handle")}
                />
                <Input
                  label="X Handle"
                  value={config.x_handle ?? ""}
                  onChange={(v) => updateConfig("x_handle", v || null)}
                  placeholder="e.g. IC_Markets"
                  discovered={discovered.has("x_handle")}
                />
              </div>
            </Section>

            {/* Research Slugs */}
            <Section title="Research Slugs" badge={slugCount} defaultOpen={slugCount > 0}>
              <div className="grid grid-cols-2 gap-3">
                <Input
                  label="WikiFX ID"
                  value={config.wikifx_id ?? ""}
                  onChange={(v) => updateConfig("wikifx_id", v || null)}
                  placeholder="e.g. 9641842942"
                  discovered={discovered.has("wikifx_id")}
                />
                <Input
                  label="TradingFinder Slug"
                  value={config.tradingfinder_slug ?? ""}
                  onChange={(v) => updateConfig("tradingfinder_slug", v || null)}
                  discovered={discovered.has("tradingfinder_slug")}
                />
                <Input
                  label="DailyForex Slug"
                  value={config.dailyforex_slug ?? ""}
                  onChange={(v) => updateConfig("dailyforex_slug", v || null)}
                  discovered={discovered.has("dailyforex_slug")}
                />
                <Input
                  label="MyFxBook Slug"
                  value={config.myfxbook_slug ?? ""}
                  onChange={(v) => updateConfig("myfxbook_slug", v || null)}
                  discovered={discovered.has("myfxbook_slug")}
                />
              </div>
            </Section>

            {/* Reputation Entities */}
            <Section title="Reputation Entities" badge={entityCount} defaultOpen={true}>
              <div className="space-y-3">
                {config.entities.map((entity, i) => (
                  <div key={i} className="rounded-lg border border-gray-100 p-3 bg-gray-50/50 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-gray-600">Entity {i + 1}</span>
                      {config.entities.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeEntity(i)}
                          className="text-gray-400 hover:text-red-500 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                    <Input
                      label="Label"
                      value={entity.label}
                      onChange={(v) => updateEntity(i, "label", v)}
                      placeholder="e.g. IC Markets (Global)"
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <Input
                        label="Trustpilot Slug"
                        value={entity.trustpilot_slug ?? ""}
                        onChange={(v) => updateEntity(i, "trustpilot_slug", v)}
                        placeholder="e.g. icmarkets.com"
                        discovered={i === 0 && discovered.has("trustpilot_slug")}
                      />
                      <Input
                        label="FPA Slug"
                        value={entity.fpa_slug ?? ""}
                        onChange={(v) => updateEntity(i, "fpa_slug", v)}
                        placeholder="e.g. ic-markets"
                      />
                      <Input
                        label="iOS App ID"
                        value={entity.ios_app_id ?? ""}
                        onChange={(v) => updateEntity(i, "ios_app_id", v)}
                        placeholder="e.g. 1552875348"
                        discovered={i === 0 && discovered.has("ios_app_id")}
                      />
                      <Input
                        label="Android Package"
                        value={entity.android_package ?? ""}
                        onChange={(v) => updateEntity(i, "android_package", v)}
                        placeholder="e.g. com.icmarkets.mobileapp"
                        discovered={i === 0 && discovered.has("android_package")}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={addEntity}
                className="text-xs text-primary hover:text-primary/80 flex items-center gap-0.5 mt-1"
              >
                <Plus className="w-3 h-3" /> Add Entity
              </button>
            </Section>

            {/* Submit */}
            <div className="flex items-center justify-between pt-2">
              {!isEdit && (
                <button
                  type="button"
                  onClick={() => {
                    setStep("input");
                    setDiscovered(new Set());
                    setDiscoveryWarnings([]);
                  }}
                  className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
                >
                  Back
                </button>
              )}
              <div className={cn("flex items-center gap-3", isEdit && "ml-auto")}>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className={cn(
                    "px-5 py-2 text-sm font-medium rounded-lg border transition-colors disabled:cursor-not-allowed",
                    saving
                      ? "bg-gray-100 text-gray-400 border-gray-200"
                      : "bg-primary text-white border-primary hover:bg-primary/90 active:bg-primary/80"
                  )}
                >
                  {saving ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin inline mr-1.5" />
                      Saving...
                    </>
                  ) : isEdit ? (
                    "Save Changes"
                  ) : (
                    "Add Competitor"
                  )}
                </button>
              </div>
            </div>
          </form>
        )}
    </>
  );
}

export function CompetitorForm({ open, onClose, editData }: Props) {
  // Use key to remount inner form when editData changes — resets all state cleanly
  const formKey = editData?.id ?? "__new__";
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <CompetitorFormInner key={formKey} onClose={onClose} editData={editData} />
      </DialogContent>
    </Dialog>
  );
}
