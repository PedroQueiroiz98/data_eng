import { describe, expect, it } from "vitest";
import { downloadUrl } from "@/lib/workspace";

describe("workspace lib", () => {
  it("downloadUrl encodes the path", () => {
    const url = downloadUrl("ws-1", "data/sub dir/arquivo com espaço.csv");
    expect(url).toContain("/workspaces/ws-1/download?path=");
    expect(url).toContain("data%2Fsub%20dir%2Farquivo%20com%20espa%C3%A7o.csv");
  });

  it("downloadUrl uses the API base", () => {
    expect(downloadUrl("x", "a.txt").startsWith("/api")).toBe(true);
  });
});
