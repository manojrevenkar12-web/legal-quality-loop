import type { LandscapeCell } from "../../shared/api/types";
import { pct } from "../../shared/format";

const FAMILIES = ["research", "review", "discovery"];

export function LandscapeSection({ cells }: { cells: LandscapeCell[] }) {
  const juris = [...new Set(cells.map((c) => c.jurisdiction))].sort();
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Task family</th>
            {juris.map((j) => (
              <th key={j} className="num">
                {j}
              </th>
            ))}
            <th>How quality is decided</th>
          </tr>
        </thead>
        <tbody>
          {FAMILIES.map((f) => {
            const row = cells.filter((c) => c.family === f);
            if (!row.length) return null;
            return (
              <tr key={f}>
                <td className="cap">{f}</td>
                {juris.map((j) => {
                  const c = row.find((x) => x.jurisdiction === j);
                  return (
                    <td key={j} className="num">
                      {c ? (
                        <>
                          {pct(c.platform_pass)}
                          <span className="sub">experts {pct(c.expert_pass)}</span>
                        </>
                      ) : (
                        "–"
                      )}
                    </td>
                  );
                })}
                <td className="measure">{row[0]!.measure}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
