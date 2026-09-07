import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { router } from "@/router";
import { queryClient } from "@/lib/queryClient";
import "@/lib/monaco";
import "@/index.css";

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("elemento #root não encontrado");

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
