// Configura o Monaco para usar o pacote empacotado (sem CDN) e um único worker.
import { loader } from "@monaco-editor/react";
import type { Environment } from "monaco-editor";
import * as monaco from "monaco-editor";
import editorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import { registerPythonIntelligence } from "@/lib/monacoProviders";

declare global {
  interface Window {
    MonacoEnvironment?: Environment;
  }
}

window.MonacoEnvironment = {
  getWorker: () => new editorWorker(),
};

loader.config({ monaco });
registerPythonIntelligence();

export {};
