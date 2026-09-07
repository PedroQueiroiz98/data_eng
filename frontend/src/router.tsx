import { createBrowserRouter, Navigate } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { RootShell } from "@/components/RootShell";
import { Dashboard } from "@/pages/Dashboard";
import { ExecutionDetail } from "@/pages/ExecutionDetail";
import { Executions } from "@/pages/Executions";
import { JobDetail } from "@/pages/JobDetail";
import { Jobs } from "@/pages/Jobs";
import { Login } from "@/pages/Login";
import { NotebookEditor } from "@/pages/NotebookEditor";
import { Notebooks } from "@/pages/Notebooks";
import { Schedules } from "@/pages/Schedules";
import { Workspace } from "@/pages/Workspace";
import { Workspaces } from "@/pages/Workspaces";
import { WorkspaceLayout } from "@/components/WorkspaceLayout";
import { Secrets } from "@/pages/Secrets";
import { Settings } from "@/pages/Settings";
import { Variables } from "@/pages/Variables";
import { WorkflowEditor } from "@/pages/WorkflowEditor";
import { Workflows } from "@/pages/Workflows";

export const router = createBrowserRouter(
  [
    {
      element: <RootShell />,
      children: [
        { path: "/login", element: <Login /> },
        {
          path: "/",
          element: <Layout />,
          children: [
            { index: true, element: <Navigate to="/dashboard" replace /> },
            { path: "dashboard", element: <Dashboard /> },
            { path: "notebooks", element: <Notebooks /> },
            { path: "notebooks/:id", element: <NotebookEditor /> },
            { path: "workspaces", element: <Workspaces /> },
            { path: "workflows", element: <Workflows /> },
            { path: "workflows/:id", element: <WorkflowEditor /> },
            { path: "jobs", element: <Jobs /> },
            { path: "jobs/:id", element: <JobDetail /> },
            { path: "executions", element: <Executions /> },
            { path: "executions/:id", element: <ExecutionDetail /> },
            { path: "schedules", element: <Schedules /> },
            { path: "variables", element: <Variables /> },
            { path: "secrets", element: <Secrets /> },
            { path: "settings", element: <Settings /> },
          ],
        },
        {
          path: "/",
          element: <WorkspaceLayout />,
          children: [{ path: "workspaces/:id", element: <Workspace /> }],
        },
      ],
    },
  ],
  { future: { v7_relativeSplatPath: true } },
);
