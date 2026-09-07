import { createBrowserRouter, Navigate } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Dashboard } from "@/pages/Dashboard";
import { ExecutionDetail } from "@/pages/ExecutionDetail";
import { Executions } from "@/pages/Executions";
import { NotebookEditor } from "@/pages/NotebookEditor";
import { Notebooks } from "@/pages/Notebooks";
import { Placeholder } from "@/pages/Placeholder";

export const router = createBrowserRouter(
  [
    {
      path: "/",
      element: <Layout />,
      children: [
        { index: true, element: <Navigate to="/dashboard" replace /> },
        { path: "dashboard", element: <Dashboard /> },
        { path: "notebooks", element: <Notebooks /> },
        { path: "notebooks/:id", element: <NotebookEditor /> },
        { path: "workflows", element: <Placeholder title="Workflows" phase={5} /> },
        { path: "workflows/:id", element: <Placeholder title="Workflow Editor" phase={5} /> },
        { path: "jobs", element: <Placeholder title="Jobs" phase={6} /> },
        { path: "jobs/:id", element: <Placeholder title="Job Details" phase={6} /> },
        { path: "executions", element: <Executions /> },
        { path: "executions/:id", element: <ExecutionDetail /> },
        { path: "schedules", element: <Placeholder title="Schedules" phase={7} /> },
        { path: "variables", element: <Placeholder title="Variables" phase={8} /> },
        { path: "secrets", element: <Placeholder title="Secrets" phase={8} /> },
        { path: "settings", element: <Placeholder title="Settings" phase={9} /> },
      ],
    },
  ],
  { future: { v7_relativeSplatPath: true } },
);
