import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { App } from "../src/app/App";
import { bestSoFar } from "../src/features/search/trajectory";
import { changedLevers, pct, signedPct } from "../src/shared/format";
import type { Results } from "../src/shared/api/types";

const results: Results = JSON.parse(readFileSync(resolve(__dirname, "../../reports/results.json"), "utf8"));

afterEach(() => vi.unstubAllGlobals());

function serve(body: unknown, status = 200) {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status })));
}

describe("helpers", () => {
  it("follows the best-so-far candidate", () => {
    const steps = bestSoFar([
      { iteration: 0, key: "a", accepted: true, change: {}, fitness: 0.5, pass: 0.5, expert_pass: 0.8 },
      { iteration: 1, key: "b", accepted: true, change: { tone: "assertive" }, fitness: 0.9, pass: 0.9, expert_pass: 0.6 },
      { iteration: 2, key: "c", accepted: true, change: {}, fitness: 0.7, pass: 0.7, expert_pass: 0.9 },
      { iteration: 2, key: "d", accepted: false, change: {} },
    ]);
    expect(steps.map((s) => [s.judge, s.expert])).toEqual([[0.5, 0.8], [0.9, 0.6], [0.9, 0.6]]);
    expect(steps[1]!.change).toEqual(["tone: assertive"]);
  });
  it("formats", () => {
    expect(pct(0.912)).toBe("91%");
    expect(signedPct(-0.175)).toBe("−17.5 pts");
    expect(changedLevers({ tone: "neutral", model: "medium" }, { tone: "assertive", model: "medium" })).toEqual(["assertive tone"]);
  });
});

describe("dashboard", () => {
  it("shows a skeleton, then the generated results", async () => {
    serve(results);
    render(<App />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading the results");
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("please the judge");
    expect(screen.getByRole("heading", { name: "Held-out legal tasks, run once" })).toBeInTheDocument();
    expect(screen.getAllByText("selected").length).toBe(1);
    expect(screen.getByText(/Flagged by the expert audit/)).toBeInTheDocument();
  });

  it("switches searches", async () => {
    serve(results);
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("tab", { name: "Scored by the calibrated judge and checks" }));
    expect(await screen.findByText(/Confirmed by the expert audit/)).toBeInTheDocument();
  });

  it("explains missing results without offering a useless retry", async () => {
    serve({}, 404);
    render(<App />);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/Run qloop develop/)).toBeInTheDocument();
    expect(within(alert).queryByRole("button")).not.toBeInTheDocument();
  });

  it("retries after a server error", async () => {
    const f = vi.fn().mockResolvedValueOnce(new Response("", { status: 503 })).mockResolvedValue(new Response(JSON.stringify(results)));
    vi.stubGlobal("fetch", f);
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("shows empty held-out sections before the held-out run", async () => {
    serve({ ...results, heldout: null });
    render(<App />);
    expect(await screen.findByText("Not run yet")).toBeInTheDocument();
    expect(screen.getByText("No gate decisions yet")).toBeInTheDocument();
  });
});
