import type { Strings } from "../i18n";
import { Camera, Megaphone, Search, Bookmark, BookmarkFilled } from "./icons";

export type Tab = "scan" | "alerts" | "claims" | "saved";

export function TabBar({ tab, onChange, s }: { tab: Tab; onChange: (t: Tab) => void; s: Strings }) {
  const items: { id: Tab; label: string; Icon: typeof Camera; Active: typeof Camera }[] = [
    { id: "scan", label: s.tabs.scan, Icon: Camera, Active: Camera },
    { id: "alerts", label: s.tabs.alerts, Icon: Megaphone, Active: Megaphone },
    { id: "claims", label: s.tabs.claims, Icon: Search, Active: Search },
    { id: "saved", label: s.tabs.saved, Icon: Bookmark, Active: BookmarkFilled },
  ];

  return (
    <nav className="tabbar" aria-label={s.appName}>
      <div className="tabbar-inner">
        {items.map(({ id, label, Icon, Active }) => {
          const active = tab === id;
          return (
            <button
              key={id}
              type="button"
              className="tab"
              aria-current={active ? "page" : undefined}
              onClick={() => onChange(id)}
            >
              {active ? <Active size={22} /> : <Icon size={22} />}
              <span>{label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
