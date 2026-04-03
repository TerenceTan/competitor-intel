"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { Card } from "@/components/ui/card";

type Account = Record<string, unknown>;

interface AccountAccordionProps {
  items: {
    competitorId: string;
    competitorName: string;
    accounts: Account[];
    isMarketSpecific: boolean;
    badge: React.ReactNode;
  }[];
}

export function AccountAccordion({ items }: AccountAccordionProps) {
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <div className="space-y-2">
      {items.map(({ competitorId, competitorName, accounts, badge }) => {
        const isOpen = openId === competitorId;
        return (
          <Card key={competitorId} className="border-gray-200 bg-white overflow-hidden">
            <button
              type="button"
              onClick={() => setOpenId(isOpen ? null : competitorId)}
              className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50/60 transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-gray-900">
                  {competitorName}
                </span>
                {badge}
                <span className="text-[11px] text-gray-400">
                  {accounts.length} account{accounts.length !== 1 ? "s" : ""}
                </span>
              </div>
              <ChevronDown
                className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? "rotate-180" : ""}`}
              />
            </button>
            {isOpen && (
              <div className="px-4 pb-3 border-t border-gray-100">
                <table className="w-full text-sm mt-2">
                  <thead>
                    <tr className="text-[11px] text-gray-500 uppercase tracking-wider">
                      <th className="text-left py-1.5 font-medium">Account</th>
                      <th className="text-left py-1.5 font-medium">Min Deposit</th>
                      <th className="text-left py-1.5 font-medium">Leverage</th>
                      <th className="text-left py-1.5 font-medium">Spread</th>
                      <th className="text-left py-1.5 font-medium">Commission</th>
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.map((acc, i) => {
                      const name = String(acc.account_name ?? acc.name ?? `Account ${i + 1}`);
                      return (
                        <tr key={i} className="border-t border-gray-50">
                          <td className="py-1.5 text-gray-800 font-medium">{name}</td>
                          <td className="py-1.5 text-gray-600 font-mono text-xs">
                            {acc.min_deposit ? String(acc.min_deposit) : <span className="text-gray-300">—</span>}
                          </td>
                          <td className="py-1.5 text-gray-700 font-mono text-xs font-semibold">
                            {acc.max_leverage ? String(acc.max_leverage) : <span className="text-gray-300">—</span>}
                          </td>
                          <td className="py-1.5 text-gray-600 font-mono text-xs">
                            {acc.spread_from ? String(acc.spread_from) : <span className="text-gray-300">—</span>}
                          </td>
                          <td className="py-1.5 text-gray-600 font-mono text-xs">
                            {acc.commission ? String(acc.commission) : <span className="text-gray-300">—</span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}
