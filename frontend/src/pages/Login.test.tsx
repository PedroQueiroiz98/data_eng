import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "@/components/AuthProvider";
import { Login } from "@/pages/Login";

const navigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => navigate };
});

afterEach(() => {
  vi.restoreAllMocks();
  navigate.mockReset();
  try {
    localStorage.clear();
  } catch {
    /* ignore */
  }
});

describe("Login", () => {
  it("faz login e navega para o dashboard", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: "tok-123",
          token_type: "bearer",
          user: { id: "u1", email: "admin@x", name: "A", role: "admin" },
        }),
        { status: 200 },
      ),
    );

    render(
      <MemoryRouter>
        <AuthProvider>
          <Login />
        </AuthProvider>
      </MemoryRouter>,
    );

    await userEvent.type(screen.getByLabelText(/E-mail/), "admin@x.com");
    await userEvent.type(screen.getByLabelText(/Senha/), "secret");
    await userEvent.click(screen.getByRole("button", { name: /Entrar/ }));

    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith("/dashboard", { replace: true }),
    );
    expect(localStorage.getItem("nbp.token")).toBe("tok-123");
  });

  it("mostra erro em credenciais inválidas", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "unauthorized" } }), { status: 401 }),
    );

    render(
      <MemoryRouter>
        <AuthProvider>
          <Login />
        </AuthProvider>
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText(/E-mail/), "a@b.com");
    await userEvent.type(screen.getByLabelText(/Senha/), "x");
    await userEvent.click(screen.getByRole("button", { name: /Entrar/ }));

    await waitFor(() =>
      expect(screen.getByText(/Credenciais inválidas/)).toBeInTheDocument(),
    );
    expect(navigate).not.toHaveBeenCalled();
  });
});
