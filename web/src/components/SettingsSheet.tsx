import { useState } from "react";
import type { Lang, Strings } from "../i18n";
import { Sheet } from "./Sheet";
import { Back, Lock, Trash } from "./icons";

export type TextSize = 100 | 115 | 130;

interface Props {
  s: Strings;
  lang: Lang;
  onLang: (l: Lang) => void;
  textSize: TextSize;
  onTextSize: (n: TextSize) => void;
  onClearData: () => void;
  onClose: () => void;
  initialHow?: boolean;
}

export function SettingsSheet({ s, lang, onLang, textSize, onTextSize, onClearData, onClose, initialHow }: Props) {
  const [how, setHow] = useState(!!initialHow);

  return (
    <Sheet onClose={onClose} label={s.settings}>
      {how ? (
        <div className="stack">
          <div className="card-head">
            <h2 className="card-title">{s.howHaskeWorks}</h2>
            <button type="button" className="icon-btn" style={{ color: "var(--ink)" }} onClick={() => setHow(false)} aria-label={s.close}>
              <Back size={22} />
            </button>
          </div>
          <p className="disclaimer">{s.howWorksBody}</p>
        </div>
      ) : (
        <div className="stack">
          <h2 className="card-title">{s.settings}</h2>

          <div className="field">
            <span className="label">{s.language}</span>
            <div className="btn-row">
              <button type="button" className={`btn ${lang === "en" ? "btn-primary" : "btn-secondary"}`} onClick={() => onLang("en")} aria-pressed={lang === "en"}>
                {s.english}
              </button>
              <button type="button" className={`btn ${lang === "pcm" ? "btn-primary" : "btn-secondary"}`} onClick={() => onLang("pcm")} aria-pressed={lang === "pcm"}>
                {s.pidgin}
              </button>
            </div>
          </div>

          <div className="field">
            <span className="label">{s.textSize}</span>
            <div style={{ display: "flex", gap: 8 }}>
              {([100, 115, 130] as TextSize[]).map((n) => (
                <button key={n} type="button" className={`btn ${textSize === n ? "btn-primary" : "btn-secondary"}`} style={{ flex: 1 }} onClick={() => onTextSize(n)} aria-pressed={textSize === n}>
                  {n === 100 ? "A" : n === 115 ? "A+" : "A++"}
                </button>
              ))}
            </div>
          </div>

          <button type="button" className="btn btn-secondary btn-block" onClick={() => setHow(true)}>
            {s.howHaskeWorks}
          </button>

          <div className="card" style={{ background: "var(--page)" }}>
            <h3 className="kicker"><Lock size={14} /> {s.privacy}</h3>
            <div className="stack">
              <p className="disclaimer">{s.privacyPhoto}</p>
              <p className="disclaimer">{s.privacyData}</p>
              <p className="disclaimer">{s.privacyAnalytics}</p>
            </div>
          </div>

          <button type="button" className="btn btn-danger btn-block" onClick={onClearData}>
            <Trash size={20} /> {s.clearData}
          </button>
        </div>
      )}
    </Sheet>
  );
}
