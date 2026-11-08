import type { InjectionRow, RedTeamPart } from "../../shared/api/types";

export function GuardrailSection({ injection, redteam }: { injection: InjectionRow[]; redteam: { development: RedTeamPart; heldout: RedTeamPart } }) {
  return (
    <div className="grid-2">
      <div>
        <h3>Injected contracts the assistant obeyed</h3>
        <table>
          <thead>
            <tr>
              <th>Defence</th>
              <th className="num">Obeyed</th>
              <th className="num">Caught on output</th>
            </tr>
          </thead>
          <tbody>
            {injection.map((r) => (
              <tr key={r.defence}>
                <td>{r.defence}</td>
                <td className={r.obeyed ? "num bad" : "num"}>
                  {r.obeyed} of {r.n}
                </td>
                <td className="num">{r.caught_by_output_check}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div>
        <h3>The input filter on its own</h3>
        <dl className="facts">
          <dt>Attacks it was built against</dt>
          <dd>
            {redteam.development.caught} of {redteam.development.attacks} caught
          </dd>
          <dt>Benign clauses mentioning instructions</dt>
          <dd>{redteam.development.false_positives.length} flagged</dd>
          <dt>Attacks written after it was finished</dt>
          <dd className={redteam.heldout.caught < redteam.heldout.attacks ? "bad" : ""}>
            {redteam.heldout.caught} of {redteam.heldout.attacks} caught
          </dd>
        </dl>
        <p className="note">
          A pattern filter learns the attacks it has seen. Fencing documents in the prompt and checking that every extracted value
          stands in the document outside injected text carry the defence.
        </p>
      </div>
    </div>
  );
}
