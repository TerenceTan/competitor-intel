"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Plus, Pencil, Trash2, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { CompetitorForm } from "./competitor-form";
import { deleteCompetitor } from "@/app/(dashboard)/admin/actions";

interface Competitor {
  id: string;
  name: string;
  tier: number;
  website: string;
  isSelf: number;
  createdAt: string;
  scraperConfig: string | null;
}

interface Props {
  competitors: Competitor[];
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export function CompetitorTable({ competitors }: Props) {
  const router = useRouter();
  const [formOpen, setFormOpen] = useState(false);
  const [editData, setEditData] = useState<Parameters<typeof CompetitorForm>[0]["editData"]>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  function handleEdit(c: Competitor) {
    let parsed = null;
    try {
      parsed = c.scraperConfig ? JSON.parse(c.scraperConfig) : null;
    } catch {
      parsed = null;
    }
    setEditData({
      id: c.id,
      name: c.name,
      tier: c.tier,
      website: c.website,
      isSelf: c.isSelf,
      scraperConfig: parsed,
    });
    setFormOpen(true);
  }

  function handleAdd() {
    setEditData(null);
    setFormOpen(true);
  }

  async function handleDelete() {
    if (!deleteId) return;
    setDeleting(true);
    await deleteCompetitor(deleteId);
    setDeleting(false);
    setDeleteId(null);
    router.refresh();
  }

  const deleteName = competitors.find((c) => c.id === deleteId)?.name ?? deleteId;

  return (
    <>
      <Card className="border-gray-200 overflow-hidden bg-white">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <span className="text-gray-700 font-medium text-sm">
            {competitors.length} competitor{competitors.length !== 1 ? "s" : ""}
          </span>
          <button
            onClick={handleAdd}
            className="px-4 py-1.5 text-xs rounded-lg border bg-primary text-white border-primary hover:bg-primary/90 active:bg-primary/80 transition-colors font-medium flex items-center gap-1"
          >
            <Plus className="w-3 h-3" />
            Add Competitor
          </button>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50/80">
              <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                ID
              </th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                Name
              </th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                Tier
              </th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                Website
              </th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                Config
              </th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                Added
              </th>
              <th className="text-right px-4 py-3 text-gray-500 font-medium text-xs uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {competitors.map((c, idx) => {
              const hasConfig = !!c.scraperConfig;
              return (
                <tr
                  key={c.id}
                  className={cn(
                    "border-b border-gray-100 hover:bg-primary/[0.03] transition-colors",
                    idx === competitors.length - 1 && "border-b-0",
                    c.isSelf && "bg-primary/[0.02]"
                  )}
                >
                  <td className="px-4 py-3 text-gray-500 font-mono text-xs">{c.id}</td>
                  <td className="px-4 py-3 text-gray-900 font-medium">
                    {c.name}
                    {c.isSelf ? (
                      <span className="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-primary/10 text-primary">
                        SELF
                      </span>
                    ) : null}
                  </td>
                  <td className="px-4 py-3 text-gray-500">T{c.tier}</td>
                  <td className="px-4 py-3">
                    <a
                      href={`https://${c.website}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-gray-500 hover:text-primary text-xs transition-colors"
                    >
                      {c.website}
                    </a>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={cn(
                        "inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium border",
                        hasConfig
                          ? "bg-green-50 text-green-700 border-green-200"
                          : "bg-gray-50 text-gray-400 border-gray-200"
                      )}
                    >
                      {hasConfig ? "Configured" : "No config"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{formatDate(c.createdAt)}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => handleEdit(c)}
                        className="p-1.5 rounded-md text-gray-400 hover:text-primary hover:bg-primary/5 transition-colors"
                        title="Edit"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      {!c.isSelf && (
                        <button
                          onClick={() => setDeleteId(c.id)}
                          className="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>

      {/* Form dialog */}
      <CompetitorForm
        open={formOpen}
        onClose={() => {
          setFormOpen(false);
          setEditData(null);
        }}
        editData={editData}
      />

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteId} onOpenChange={(v) => !v && setDeleteId(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Delete competitor</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-600">
            Are you sure you want to delete <strong>{deleteName}</strong>? This will remove the
            competitor config but existing snapshot data will be preserved.
          </p>
          <div className="flex justify-end gap-3 mt-4">
            <button
              onClick={() => setDeleteId(null)}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 active:bg-red-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {deleting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin inline mr-1.5" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
