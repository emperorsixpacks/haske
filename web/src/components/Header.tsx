import type { Strings } from "../i18n";
import { Gear, HaskeMark } from "./icons";

export function Header({ s, onSettings }: { s: Strings; onSettings: () => void }) {
  return (
    <header className="header">
      <div className="header-inner">
        <HaskeMark size={26} />
        <div>
          <div className="header-title">{s.appName}</div>
          <div className="header-sub">{s.appTagline}</div>
        </div>
        <div className="header-spacer" />
        <button type="button" className="icon-btn" onClick={onSettings} aria-label={s.settings}>
          <Gear size={22} />
        </button>
      </div>
    </header>
  );
}
